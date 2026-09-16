import os
import secrets
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db
from ticket_pricing import CinemaShow, TicketTier, calculate_bill


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "ticket_pricing.db"))


def create_app(test_config=None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-this"),
        DATABASE=DATABASE,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    )
    if test_config:
        app.config.update(test_config)

    from database import close_db, get_db, init_db, seed_db

    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db(app.config["DATABASE"])
        seed_db(get_db())

    @app.before_request
    def load_user():
        session.setdefault("csrf_token", secrets.token_urlsafe(24))
        if request.method == "POST":
            submitted_token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not submitted_token or not secrets.compare_digest(submitted_token, session["csrf_token"]):
                return render_template("error.html", message="Invalid form security token."), 400
        g.user = None
        user_id = session.get("user_id")
        auth_token = session.get("auth_token")
        if user_id and auth_token:
            user = get_db().execute(
                "SELECT u.* FROM users u JOIN auth_sessions s ON s.user_id = u.id "
                "WHERE u.id = ? AND s.token = ? AND s.expires_at > ?",
                (user_id, auth_token, utc_now()),
            ).fetchone()
            if user:
                g.user = user
            else:
                session.clear()

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)

        return wrapped

    def admin_required(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] != "admin":
                flash("Admin access is required.", "error")
                return redirect(url_for("index"))
            return view(*args, **kwargs)

        return wrapped

    @app.context_processor
    def inject_helpers():
        return {"now": utc_now(), "csrf_token": session.get("csrf_token")}

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", message="Page not found."), 404

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("error.html", message="Something went wrong. Please try again."), 500

    @app.route("/")
    def index():
        search = request.args.get("q", "").strip()
        date = request.args.get("date", "").strip()
        query = "SELECT * FROM shows"
        filters = []
        params = []
        if search:
            filters.append("(show_name LIKE ? OR cinema_name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if date:
            filters.append("starts_at LIKE ?")
            params.append(f"{date}%")
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY starts_at"
        shows = get_db().execute(query, params).fetchall()
        return render_template("index.html", shows=shows, search=search, date=date)

    @app.route("/health")
    def health():
        get_db().execute("SELECT 1")
        return jsonify({"status": "ok"})

    @app.route("/register", methods=("GET", "POST"))
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not name or "@" not in email or len(password) < 8:
                flash("Enter a name, valid email, and password of at least 8 characters.", "error")
                return render_template("register.html")
            db = get_db()
            try:
                cursor = db.execute(
                    "INSERT INTO users (name, email, password_hash, role, verified) VALUES (?, ?, ?, 'customer', 0)",
                    (name, email, generate_password_hash(password)),
                )
                token = create_token(db, "verification_tokens", "user_id", cursor.lastrowid)
                db.commit()
                flash("Account created. Verify your email using the development link below.", "success")
                return render_template("register.html", verification_url=url_for("verify_email", token=token))
            except sqlite3.IntegrityError:
                db.rollback()
                flash("That email is already registered.", "error")
        return render_template("register.html")

    @app.route("/verify/<token>")
    def verify_email(token):
        db = get_db()
        record = db.execute(
            "SELECT user_id FROM verification_tokens WHERE token = ? AND expires_at > ?",
            (token, utc_now()),
        ).fetchone()
        if not record:
            flash("That verification link is invalid or expired.", "error")
        else:
            db.execute("UPDATE users SET verified = 1 WHERE id = ?", (record["user_id"],))
            db.execute("DELETE FROM verification_tokens WHERE token = ?", (token,))
            db.commit()
            flash("Email verified. You can now log in.", "success")
        return redirect(url_for("login"))

    @app.route("/login", methods=("GET", "POST"))
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not user or not check_password_hash(user["password_hash"], request.form.get("password", "")):
                flash("Invalid email or password.", "error")
            elif not user["verified"]:
                flash("Please verify your email before logging in.", "error")
            else:
                db = get_db()
                token = secrets.token_urlsafe(32)
                db.execute(
                    "INSERT INTO auth_sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
                    (user["id"], token, (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()),
                )
                db.commit()
                session.clear()
                session.update(user_id=user["id"], auth_token=token)
                return redirect(request.args.get("next") or url_for("index"))
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        if session.get("auth_token"):
            get_db().execute("DELETE FROM auth_sessions WHERE token = ?", (session["auth_token"],))
            get_db().commit()
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("index"))

    @app.route("/profile", methods=("GET", "POST"))
    @login_required
    def profile():
        db = get_db()
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            new_password = request.form.get("new_password", "")
            if not name:
                flash("Name cannot be empty.", "error")
            elif new_password and len(new_password) < 8:
                flash("New password must be at least 8 characters.", "error")
            else:
                db.execute("UPDATE users SET name=? WHERE id=?", (name, g.user["id"]))
                if new_password:
                    db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), g.user["id"]))
                db.commit()
                flash("Profile updated.", "success")
                return redirect(url_for("profile"))
        return render_template("profile.html")

    @app.route("/forgot-password", methods=("GET", "POST"))
    def forgot_password():
        reset_url = None
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = get_db().execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if user:
                token = create_token(get_db(), "password_reset_tokens", "user_id", user["id"])
                get_db().commit()
                reset_url = url_for("reset_password", token=token)
            flash("If the account exists, a reset link has been generated.", "success")
        return render_template("forgot_password.html", reset_url=reset_url)

    @app.route("/reset-password/<token>", methods=("GET", "POST"))
    def reset_password(token):
        db = get_db()
        record = db.execute(
            "SELECT user_id FROM password_reset_tokens WHERE token = ? AND expires_at > ?",
            (token, utc_now()),
        ).fetchone()
        if not record:
            flash("That reset link is invalid or expired.", "error")
            return redirect(url_for("forgot_password"))
        if request.method == "POST":
            password = request.form.get("password", "")
            if len(password) < 8:
                flash("Password must be at least 8 characters.", "error")
            else:
                db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password), record["user_id"]))
                db.execute("DELETE FROM password_reset_tokens WHERE token = ?", (token,))
                db.commit()
                flash("Password updated. Please log in.", "success")
                return redirect(url_for("login"))
        return render_template("reset_password.html")

    @app.route("/shows/<int:show_id>")
    def show_detail(show_id):
        db = get_db()
        show = db.execute("SELECT * FROM shows WHERE id = ?", (show_id,)).fetchone()
        if not show:
            return render_template("error.html", message="Show not found."), 404
        release_expired_holds(db)
        multiplier = demand_multiplier(db, show_id)
        tiers = [{**dict(tier), "price": dynamic_price(tier["price"], multiplier)} for tier in db.execute("SELECT * FROM ticket_tiers WHERE show_id = ? ORDER BY price", (show_id,)).fetchall()]
        seats = db.execute("SELECT s.id, s.seat_number, s.tier_id, s.status, t.price FROM seats s JOIN ticket_tiers t ON t.id=s.tier_id WHERE s.show_id = ? ORDER BY s.seat_number", (show_id,)).fetchall()
        return render_template("show_detail.html", show=show, tiers=tiers, seats=seats, demand_multiplier=multiplier)

    @app.route("/api/shows/<int:show_id>/availability")
    def availability(show_id):
        db = get_db()
        release_expired_holds(db)
        rows = db.execute(
            "SELECT s.seat_number, s.status, t.name AS tier FROM seats s JOIN ticket_tiers t ON t.id=s.tier_id WHERE s.show_id=? ORDER BY s.seat_number",
            (show_id,),
        ).fetchall()
        return jsonify([dict(row) for row in rows])

    @app.route("/book", methods=("POST",))
    @login_required
    def book():
        db = get_db()
        seat_ids = request.form.getlist("seat_ids")
        show_id = request.form.get("show_id", type=int)
        passenger_name = request.form.get("passenger_name", "").strip()
        passenger_email = request.form.get("passenger_email", "").strip()
        if not seat_ids or not show_id or not passenger_name or "@" not in passenger_email:
            flash("Select at least one available seat and enter passenger details.", "error")
            return redirect(url_for("show_detail", show_id=show_id))
        try:
            db.execute("BEGIN IMMEDIATE")
            release_expired_holds(db, commit=False)
            placeholders = ",".join("?" for _ in seat_ids)
            seats = db.execute(
                f"SELECT s.*, t.name AS tier_name, t.price FROM seats s JOIN ticket_tiers t ON t.id=s.tier_id WHERE s.show_id=? AND s.id IN ({placeholders}) AND s.status='available'",
                [show_id, *seat_ids],
            ).fetchall()
            if len(seats) != len(set(seat_ids)):
                raise ValueError("One or more selected seats are no longer available.")
            multiplier = demand_multiplier(db, show_id)
            seats = [{**dict(seat), "price": str(dynamic_price(seat["price"], multiplier))} for seat in seats]
            show = db.execute("SELECT * FROM shows WHERE id=?", (show_id,)).fetchone()
            bill, tier_lines = calculate_selected_bill(show, seats)
            reference = "TP-" + secrets.token_hex(5).upper()
            cursor = db.execute(
                "INSERT INTO bookings (reference, user_id, show_id, tier_id, quantity, status, total_amount, hold_expires_at) VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)",
                (reference, g.user["id"], show_id, seats[0]["tier_id"], len(seats), str(bill.total), (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()),
            )
            booking_id = cursor.lastrowid
            for seat in seats:
                db.execute("UPDATE seats SET status='held' WHERE id=?", (seat["id"],))
                db.execute("INSERT INTO booking_items (booking_id, seat_id, price) VALUES (?, ?, ?)", (booking_id, seat["id"], seat["price"]))
            db.execute("INSERT INTO passengers (booking_id, name, email) VALUES (?, ?, ?)", (booking_id, passenger_name, passenger_email))
            db.execute("INSERT INTO payments (booking_id, provider, status, amount) VALUES (?, 'mock', 'pending', ?)", (booking_id, str(bill.total)))
            db.commit()
            session[f"bill_{booking_id}"] = {"ticket_lines": tier_lines, "ticket_total": str(bill.ticket_total), "festival_discount": str(bill.festival_discount), "member_discount": str(bill.member_discount), "discounted_ticket_total": str(bill.discounted_ticket_total), "convenience_fee": str(bill.convenience_fee), "taxable_total": str(bill.taxable_total), "gst": str(bill.gst), "total": str(bill.total)}
            return redirect(url_for("payment", booking_id=booking_id))
        except (ValueError, sqlite3.Error) as error:
            db.rollback()
            flash(str(error), "error")
            return redirect(url_for("show_detail", show_id=show_id))

    @app.route("/payment/<int:booking_id>")
    @login_required
    def payment(booking_id):
        booking = get_owned_booking(booking_id)
        if not booking:
            return render_template("error.html", message="Booking not found."), 404
        bill = session.get(f"bill_{booking_id}") or booking_bill_from_database(booking)
        return render_template("payment.html", booking=booking, bill=bill)

    @app.route("/payment/<int:booking_id>/<result>")
    @login_required
    def payment_result(booking_id, result):
        db = get_db()
        booking = get_owned_booking(booking_id)
        if not booking or result not in {"success", "failure", "cancel"}:
            return render_template("error.html", message="Payment request not found."), 404
        if booking["status"] != "PENDING":
            return redirect(url_for("booking_detail", booking_id=booking_id))
        if result == "success":
            db.execute("UPDATE bookings SET status='CONFIRMED', hold_expires_at=NULL WHERE id=?", (booking_id,))
            db.execute("UPDATE seats SET status='booked' WHERE id IN (SELECT seat_id FROM booking_items WHERE booking_id=?)", (booking_id,))
            db.execute("UPDATE payments SET status='paid', provider_reference=? WHERE booking_id=?", ("MOCK-" + secrets.token_hex(4).upper(), booking_id))
            db.execute("INSERT INTO notifications (user_id, kind, message) VALUES (?, 'booking', ?)", (g.user["id"], f"Booking {booking['reference']} is confirmed."))
            flash("Payment verified and booking confirmed.", "success")
        else:
            db.execute("UPDATE bookings SET status='CANCELLED', hold_expires_at=NULL WHERE id=?", (booking_id,))
            db.execute("UPDATE seats SET status='available' WHERE id IN (SELECT seat_id FROM booking_items WHERE booking_id=?)", (booking_id,))
            db.execute("UPDATE payments SET status=? WHERE booking_id=?", ("failed" if result == "failure" else "cancelled", booking_id))
            flash("Payment was not completed. The seats were released.", "error")
        db.commit()
        return redirect(url_for("booking_detail", booking_id=booking_id))

    @app.route("/bookings")
    @login_required
    def bookings():
        status = request.args.get("status", "").upper()
        query = "SELECT b.*, s.show_name, s.starts_at FROM bookings b JOIN shows s ON s.id=b.show_id WHERE b.user_id=?"
        params = [g.user["id"]]
        if status in {"PENDING", "CONFIRMED", "CANCELLED"}:
            query += " AND b.status=?"
            params.append(status)
        query += " ORDER BY b.created_at DESC LIMIT 100"
        rows = get_db().execute(query, params).fetchall()
        return render_template("bookings.html", bookings=rows)

    @app.route("/api/bookings/<int:booking_id>")
    @login_required
    def booking_api(booking_id):
        booking = get_owned_booking(booking_id)
        if not booking:
            return jsonify({"error": "Booking not found"}), 404
        return jsonify(dict(booking))

    @app.route("/bookings/<int:booking_id>")
    @login_required
    def booking_detail(booking_id):
        booking = get_owned_booking(booking_id)
        if not booking:
            return render_template("error.html", message="Booking not found."), 404
        seats = get_db().execute("SELECT s.seat_number FROM booking_items i JOIN seats s ON s.id=i.seat_id WHERE i.booking_id=?", (booking_id,)).fetchall()
        passenger = get_db().execute("SELECT * FROM passengers WHERE booking_id=?", (booking_id,)).fetchone()
        refund = get_db().execute("SELECT * FROM refunds WHERE booking_id=? ORDER BY id DESC LIMIT 1", (booking_id,)).fetchone()
        return render_template("booking_detail.html", booking=booking, seats=seats, passenger=passenger, refund=refund)

    @app.route("/bookings/<int:booking_id>/cancel", methods=("POST",))
    @login_required
    def cancel_booking(booking_id):
        db = get_db()
        booking = get_owned_booking(booking_id)
        if not booking or booking["status"] != "CONFIRMED":
            flash("This booking cannot be cancelled.", "error")
        else:
            db.execute("UPDATE bookings SET status='CANCELLED' WHERE id=?", (booking_id,))
            db.execute("UPDATE seats SET status='available' WHERE id IN (SELECT seat_id FROM booking_items WHERE booking_id=?)", (booking_id,))
            db.execute("INSERT INTO refunds (booking_id, status, amount) VALUES (?, 'requested', ?)", (booking_id, booking["total_amount"]))
            db.execute("INSERT INTO notifications (user_id, kind, message) VALUES (?, 'cancellation', ?)", (g.user["id"], f"Booking {booking['reference']} was cancelled and its refund was requested."))
            db.commit()
            flash("Booking cancelled. Refund requested.", "success")
        return redirect(url_for("booking_detail", booking_id=booking_id))

    @app.route("/ticket/<int:booking_id>")
    @login_required
    def ticket(booking_id):
        booking = get_owned_booking(booking_id)
        if not booking or booking["status"] != "CONFIRMED":
            return render_template("error.html", message="A confirmed ticket is required."), 404
        seats = get_db().execute("SELECT s.seat_number FROM booking_items i JOIN seats s ON s.id=i.seat_id WHERE i.booking_id=?", (booking_id,)).fetchall()
        return render_template("ticket.html", booking=booking, seats=seats)

    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        db = get_db()
        stats = {"users": db.execute("SELECT COUNT(*) FROM users WHERE role='customer'").fetchone()[0], "shows": db.execute("SELECT COUNT(*) FROM shows").fetchone()[0], "bookings": db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0], "revenue": db.execute("SELECT COALESCE(SUM(total_amount), 0) FROM bookings WHERE status='CONFIRMED'").fetchone()[0]}
        shows = db.execute("SELECT * FROM shows ORDER BY starts_at").fetchall()
        selected_show_id = request.args.get("show_id", type=int) or (shows[0]["id"] if shows else None)
        analytics = build_show_analytics(db, selected_show_id) if selected_show_id else empty_analytics()
        return render_template("admin.html", stats=stats, shows=shows, analytics=analytics, selected_show_id=selected_show_id)

    @app.route("/admin/analytics/<int:show_id>")
    @admin_required
    def admin_analytics(show_id):
        analytics = build_show_analytics(get_db(), show_id)
        if not analytics["show"]:
            return jsonify({"error": "Show not found"}), 404
        return jsonify(analytics)

    @app.route("/admin/bookings")
    @admin_required
    def admin_bookings():
        search = request.args.get("q", "").strip()
        rows = get_db().execute(
            "SELECT b.*, u.email, s.show_name FROM bookings b JOIN users u ON u.id=b.user_id JOIN shows s ON s.id=b.show_id WHERE b.reference LIKE ? OR u.email LIKE ? ORDER BY b.created_at DESC LIMIT 100",
            (f"%{search}%", f"%{search}%"),
        ).fetchall()
        return render_template("admin_bookings.html", bookings=rows, search=search)

    @app.route("/admin/shows", methods=("POST",))
    @admin_required
    def admin_create_show():
        db = get_db()
        try:
            cursor = db.execute(
                "INSERT INTO shows (cinema_name, show_name, starts_at, festival_discount, member_percent, member_discount_cap, convenience_fee, gst_percent) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (request.form["cinema_name"], request.form["show_name"], request.form["starts_at"], request.form.get("festival_discount", 0), request.form.get("member_percent", 0), request.form.get("member_discount_cap", 0), request.form.get("convenience_fee", 0), request.form.get("gst_percent", 18)),
            )
            for tier_name in ("Silver", "Gold", "Recliner"):
                price = request.form.get(f"{tier_name.lower()}_price", "0")
                count = int(request.form.get(f"{tier_name.lower()}_seats", "0"))
                tier_cursor = db.execute("INSERT INTO ticket_tiers (show_id, name, price) VALUES (?, ?, ?)", (cursor.lastrowid, tier_name, price))
                for number in range(1, count + 1):
                    db.execute("INSERT INTO seats (show_id, tier_id, seat_number, status) VALUES (?, ?, ?, 'available')", (cursor.lastrowid, tier_cursor.lastrowid, f"{tier_name[0]}{number}"))
            db.commit()
            flash("Show created.", "success")
        except (ValueError, sqlite3.Error) as error:
            db.rollback()
            flash(f"Could not create show: {error}", "error")
        return redirect(url_for("admin_dashboard"))

    return app


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def empty_analytics():
    return {
        "show": None,
        "audience": 0,
        "revenue": "0.00",
        "occupancy": 0,
        "total_seats": 0,
        "booked_seats": 0,
        "held_seats": 0,
        "tiers": [],
        "seats": [],
        "comparison": [],
    }


def demand_multiplier(db, show_id):
    counts = db.execute("SELECT COUNT(*) AS total, SUM(status IN ('booked', 'held')) AS committed FROM seats WHERE show_id=?", (show_id,)).fetchone()
    total = counts["total"] or 0
    committed = counts["committed"] or 0
    occupancy = (committed / total) if total else 0
    if occupancy >= 0.8:
        return Decimal("1.20")
    if occupancy >= 0.5:
        return Decimal("1.10")
    return Decimal("1.00")


def dynamic_price(price, multiplier):
    return (Decimal(str(price)) * multiplier).quantize(Decimal("0.01"))


def build_show_analytics(db, show_id):
    show = db.execute("SELECT id, show_name, cinema_name, starts_at FROM shows WHERE id=?", (show_id,)).fetchone()
    if not show:
        return empty_analytics()

    seat_counts = db.execute(
        "SELECT COUNT(*) AS total, SUM(status='booked') AS booked, SUM(status='held') AS held FROM seats WHERE show_id=?",
        (show_id,),
    ).fetchone()
    booking_stats = db.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS audience, COALESCE(SUM(total_amount), 0) AS revenue FROM bookings WHERE show_id=? AND status='CONFIRMED'",
        (show_id,),
    ).fetchone()
    total_seats = seat_counts["total"] or 0
    booked_seats = seat_counts["booked"] or 0
    tiers = db.execute(
        "SELECT t.name, COUNT(s.id) AS capacity, SUM(s.status='booked') AS booked, COALESCE(SUM(CASE WHEN b.status='CONFIRMED' THEN i.price ELSE 0 END), 0) AS revenue "
        "FROM ticket_tiers t LEFT JOIN seats s ON s.tier_id=t.id LEFT JOIN booking_items i ON i.seat_id=s.id LEFT JOIN bookings b ON b.id=i.booking_id "
        "WHERE t.show_id=? GROUP BY t.id ORDER BY t.price",
        (show_id,),
    ).fetchall()
    seats = db.execute(
        "SELECT seat_number, status, t.name AS tier FROM seats s JOIN ticket_tiers t ON t.id=s.tier_id WHERE s.show_id=? ORDER BY t.price, s.seat_number",
        (show_id,),
    ).fetchall()
    comparison = db.execute(
        "SELECT s.id, s.show_name, COUNT(se.id) AS capacity, SUM(se.status='booked') AS booked "
        "FROM shows s LEFT JOIN seats se ON se.show_id=s.id GROUP BY s.id ORDER BY s.starts_at",
    ).fetchall()
    return {
        "show": dict(show),
        "audience": booking_stats["audience"],
        "revenue": f"{Decimal(str(booking_stats['revenue'] or 0)):.2f}",
        "occupancy": round((booked_seats / total_seats) * 100) if total_seats else 0,
        "total_seats": total_seats,
        "booked_seats": booked_seats,
        "held_seats": seat_counts["held"] or 0,
        "tiers": [
            {"name": row["name"], "capacity": row["capacity"] or 0, "booked": row["booked"] or 0, "occupancy": round(((row["booked"] or 0) / row["capacity"]) * 100) if row["capacity"] else 0, "revenue": f"{Decimal(str(row['revenue'] or 0)):.2f}"}
            for row in tiers
        ],
        "seats": [dict(row) for row in seats],
        "comparison": [{"name": row["show_name"], "capacity": row["capacity"] or 0, "booked": row["booked"] or 0, "occupancy": round(((row["booked"] or 0) / row["capacity"]) * 100) if row["capacity"] else 0} for row in comparison],
    }


def calculate_selected_bill(show, seats):
    """Price a basket that may contain seats from several ticket tiers."""
    tier_totals = defaultdict(lambda: {"quantity": 0, "total": Decimal("0.00")})
    ticket_total = Decimal("0.00")
    for seat in seats:
        price = Decimal(str(seat["price"])).quantize(Decimal("0.01"))
        tier_totals[seat["tier_name"]]["quantity"] += 1
        tier_totals[seat["tier_name"]]["total"] += price
        ticket_total += price

    # Use the existing pure pricing function for basket-wide discount, fee,
    # GST, and rounding rules. The synthetic tier represents the full basket.
    pricing_show = CinemaShow(
        show["cinema_name"],
        show["show_name"],
        {"Selected seats": TicketTier("Selected seats", ticket_total, 1)},
    )
    bill = calculate_bill(
        pricing_show,
        "Selected seats",
        1,
        show["festival_discount"],
        show["member_percent"],
        show["member_discount_cap"],
        Decimal(str(show["convenience_fee"])) * len(seats),
        show["gst_percent"],
    )
    tier_lines = [
        {"name": name, "quantity": values["quantity"], "total": str(values["total"])}
        for name, values in tier_totals.items()
    ]
    return bill, tier_lines


def booking_bill_from_database(booking):
    db = get_db()
    seats = db.execute(
        "SELECT t.name AS tier_name, i.price FROM booking_items i JOIN seats s ON s.id=i.seat_id JOIN ticket_tiers t ON t.id=s.tier_id WHERE i.booking_id=?",
        (booking["id"],),
    ).fetchall()
    show = db.execute("SELECT * FROM shows WHERE id=?", (booking["show_id"],)).fetchone()
    bill, tier_lines = calculate_selected_bill(show, seats)
    return {"ticket_lines": tier_lines, "ticket_total": str(bill.ticket_total), "festival_discount": str(bill.festival_discount), "member_discount": str(bill.member_discount), "discounted_ticket_total": str(bill.discounted_ticket_total), "convenience_fee": str(bill.convenience_fee), "taxable_total": str(bill.taxable_total), "gst": str(bill.gst), "total": str(bill.total)}


def create_token(db, table, column, user_id):
    token = secrets.token_urlsafe(32)
    db.execute(f"INSERT INTO {table} ({column}, token, expires_at) VALUES (?, ?, ?)", (user_id, token, (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()))
    return token


def release_expired_holds(db, commit=True):
    expired = db.execute("SELECT id FROM bookings WHERE status='PENDING' AND hold_expires_at < ?", (utc_now(),)).fetchall()
    for booking in expired:
        db.execute("UPDATE seats SET status='available' WHERE id IN (SELECT seat_id FROM booking_items WHERE booking_id=?)", (booking["id"],))
        db.execute("UPDATE bookings SET status='CANCELLED' WHERE id=?", (booking["id"],))
    if commit:
        db.commit()


def get_owned_booking(booking_id):
    return get_db().execute(
        "SELECT b.*, s.cinema_name, s.show_name, s.starts_at, t.name AS tier_name FROM bookings b JOIN shows s ON s.id=b.show_id JOIN ticket_tiers t ON t.id=b.tier_id WHERE b.id=? AND b.user_id=?",
        (booking_id, g.user["id"]),
    ).fetchone()


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )