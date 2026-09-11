from flask import Flask, render_template, request, jsonify
from database import get_db, init_db

import secrets
import string


# ==================================================
# FLASK APPLICATION
# ==================================================

app = Flask(__name__)


# ==================================================
# INITIALIZE DATABASE
# ==================================================

init_db()


# ==================================================
# GENERATE UNIQUE PRIVACY ALIAS
# ==================================================

def generate_alias():

    characters = string.ascii_lowercase + string.digits

    random_part = ''.join(
        secrets.choice(characters)
        for _ in range(10)
    )

    alias = f"alias-{random_part}@aliasguard.demo"

    return alias


# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
def home():

    return render_template("index.html")


# ==================================================
# CREATE PRIVACY ALIAS
# ==================================================

@app.route("/api/create-alias", methods=["POST"])
def create_alias():

    data = request.get_json() or {}

    service = data.get("service")
    purpose = data.get("purpose")
    trust = data.get("trust")


    # ----------------------------------------------
    # VALIDATION
    # ----------------------------------------------

    if not service:

        return jsonify({
            "error": "Website / Organization is required."
        }), 400


    if trust not in ["low", "medium", "high"]:

        trust = "medium"


    # ----------------------------------------------
    # INITIAL RISK SCORE
    # ----------------------------------------------

    if trust == "low":

        risk = 30

    elif trust == "medium":

        risk = 15

    else:

        risk = 5


    # ----------------------------------------------
    # GENERATE ALIAS
    # ----------------------------------------------

    alias = generate_alias()


    # ----------------------------------------------
    # SAVE ALIAS
    # ----------------------------------------------

    conn = get_db()

    conn.execute(
        """
        INSERT INTO aliases
        (
            alias,
            service,
            purpose,
            trust_level,
            status,
            risk_score
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            alias,
            service,
            purpose,
            trust,
            "ACTIVE",
            risk
        )
    )


    # ----------------------------------------------
    # SECURITY EVENT
    # ----------------------------------------------

    conn.execute(
        """
        INSERT INTO events
        (
            alias,
            event_type,
            description
        )
        VALUES (?, ?, ?)
        """,
        (
            alias,
            "ALIAS_CREATED",
            f"Privacy alias created for {service}"
        )
    )


    conn.commit()
    conn.close()


    return jsonify({

        "success": True,

        "alias": alias,

        "service": service,

        "risk": risk

    })


# ==================================================
# DASHBOARD DATA
# ==================================================

@app.route("/api/dashboard")
def dashboard():

    conn = get_db()


    # ----------------------------------------------
    # GET ALIASES
    # ----------------------------------------------

    aliases = conn.execute(
        """
        SELECT *
        FROM aliases
        ORDER BY id DESC
        """
    ).fetchall()


    # ----------------------------------------------
    # GET EVENTS
    # ----------------------------------------------

    events = conn.execute(
        """
        SELECT *
        FROM events
        ORDER BY id DESC
        LIMIT 30
        """
    ).fetchall()


    conn.close()


    # ----------------------------------------------
    # CONVERT SQLITE ROWS TO DICTIONARIES
    # ----------------------------------------------

    aliases_data = [
        dict(row)
        for row in aliases
    ]


    events_data = [
        dict(row)
        for row in events
    ]


    # ----------------------------------------------
    # STATISTICS
    # ----------------------------------------------

    total_aliases = len(aliases_data)


    active_aliases = sum(
        1
        for alias in aliases_data
        if alias["status"] == "ACTIVE"
    )


    total_messages = sum(
        alias["messages"]
        for alias in aliases_data
    )


    exposure_reports = sum(
        alias["leaked"]
        for alias in aliases_data
    )


    return jsonify({

        "aliases": aliases_data,

        "events": events_data,

        "stats": {

            "total": total_aliases,

            "active": active_aliases,

            "messages": total_messages,

            "exposures": exposure_reports

        }

    })


# ==================================================
# SIMULATE INCOMING MESSAGE
# ==================================================

@app.route("/api/simulate-message", methods=["POST"])
def simulate_message():

    data = request.get_json() or {}

    alias = data.get("alias")


    if not alias:

        return jsonify({

            "error": "Alias is required."

        }), 400


    conn = get_db()


    # ----------------------------------------------
    # FIND ALIAS
    # ----------------------------------------------

    row = conn.execute(
        """
        SELECT *
        FROM aliases
        WHERE alias = ?
        """,
        (alias,)
    ).fetchone()


    if not row:

        conn.close()

        return jsonify({

            "error": "Alias not found."

        }), 404


    # ----------------------------------------------
    # CHECK ALIAS STATUS
    # ----------------------------------------------

    if row["status"] != "ACTIVE":

        conn.execute(
            """
            INSERT INTO events
            (
                alias,
                event_type,
                description
            )
            VALUES (?, ?, ?)
            """,
            (
                alias,
                "MESSAGE_BLOCKED",
                "Incoming message blocked because the alias is disabled."
            )
        )


        conn.commit()
        conn.close()


        return jsonify({

            "success": True,

            "blocked": True,

            "message":
                "MESSAGE BLOCKED — Alias is disabled."

        })


    # ----------------------------------------------
    # INCREASE MESSAGE COUNT
    # ----------------------------------------------

    new_message_count = row["messages"] + 1


    conn.execute(
        """
        UPDATE aliases
        SET messages = ?
        WHERE alias = ?
        """,
        (
            new_message_count,
            alias
        )
    )


    # ----------------------------------------------
    # CREATE EVENT
    # ----------------------------------------------

    conn.execute(
        """
        INSERT INTO events
        (
            alias,
            event_type,
            description
        )
        VALUES (?, ?, ?)
        """,
        (
            alias,
            "MESSAGE_RECEIVED",
            f"Message received for {row['service']}."
        )
    )


    conn.commit()
    conn.close()


    return jsonify({

        "success": True,

        "blocked": False,

        "service": row["service"],

        "message":
            f"MESSAGE RECEIVED — Attributed to {row['service']}."

    })


# ==================================================
# REPORT EXPOSURE / LEAK
# ==================================================

@app.route("/api/report-leak", methods=["POST"])
def report_leak():

    data = request.get_json() or {}

    alias = data.get("alias")


    if not alias:

        return jsonify({

            "error": "Alias is required."

        }), 400


    conn = get_db()


    # ----------------------------------------------
    # FIND ALIAS
    # ----------------------------------------------

    row = conn.execute(
        """
        SELECT *
        FROM aliases
        WHERE alias = ?
        """,
        (alias,)
    ).fetchone()


    if not row:

        conn.close()

        return jsonify({

            "error": "Alias not found."

        }), 404


    # ----------------------------------------------
    # CALCULATE RISK
    # ----------------------------------------------

    new_risk = min(
        row["risk_score"] + 50,
        100
    )


    # ----------------------------------------------
    # MARK AS LEAKED
    # ----------------------------------------------

    conn.execute(
        """
        UPDATE aliases
        SET leaked = 1,
            risk_score = ?
        WHERE alias = ?
        """,
        (
            new_risk,
            alias
        )
    )


    # ----------------------------------------------
    # SECURITY EVENT
    # ----------------------------------------------

    conn.execute(
        """
        INSERT INTO events
        (
            alias,
            event_type,
            description
        )
        VALUES (?, ?, ?)
        """,
        (
            alias,
            "EXPOSURE_DETECTED",
            f"Possible identity exposure detected for {row['service']}."
        )
    )


    conn.commit()
    conn.close()


    return jsonify({

        "success": True,

        "risk_score": new_risk,

        "risk": new_risk,

        "message":
            "POSSIBLE EXPOSURE DETECTED."

    })


# ==================================================
# DISABLE ALIAS
# ==================================================

@app.route("/api/disable-alias", methods=["POST"])
def disable_alias():

    data = request.get_json() or {}

    alias = data.get("alias")


    if not alias:

        return jsonify({

            "error": "Alias is required."

        }), 400


    conn = get_db()


    # ----------------------------------------------
    # FIND ALIAS
    # ----------------------------------------------

    row = conn.execute(
        """
        SELECT *
        FROM aliases
        WHERE alias = ?
        """,
        (alias,)
    ).fetchone()


    if not row:

        conn.close()

        return jsonify({

            "error": "Alias not found."

        }), 404


    # ----------------------------------------------
    # DISABLE ALIAS
    # ----------------------------------------------

    conn.execute(
        """
        UPDATE aliases
        SET status = 'DISABLED'
        WHERE alias = ?
        """,
        (alias,)
    )


    # ----------------------------------------------
    # SECURITY EVENT
    # ----------------------------------------------

    conn.execute(
        """
        INSERT INTO events
        (
            alias,
            event_type,
            description
        )
        VALUES (?, ?, ?)
        """,
        (
            alias,
            "ALIAS_DISABLED",
            f"Alias disabled for {row['service']}."
        )
    )


    conn.commit()
    conn.close()


    return jsonify({

        "success": True,

        "message":
            "Alias disabled successfully."

    })


# ==================================================
# ENABLE / REACTIVATE ALIAS
# ==================================================

@app.route("/api/enable-alias", methods=["POST"])
def enable_alias():

    data = request.get_json() or {}

    alias = data.get("alias")


    if not alias:

        return jsonify({

            "error": "Alias is required."

        }), 400


    conn = get_db()


    # ----------------------------------------------
    # FIND ALIAS
    # ----------------------------------------------

    row = conn.execute(
        """
        SELECT *
        FROM aliases
        WHERE alias = ?
        """,
        (alias,)
    ).fetchone()


    if not row:

        conn.close()

        return jsonify({

            "error": "Alias not found."

        }), 404


    # ----------------------------------------------
    # ENABLE ALIAS
    # ----------------------------------------------

    conn.execute(
        """
        UPDATE aliases
        SET status = 'ACTIVE'
        WHERE alias = ?
        """,
        (alias,)
    )


    # ----------------------------------------------
    # SECURITY EVENT
    # ----------------------------------------------

    conn.execute(
        """
        INSERT INTO events
        (
            alias,
            event_type,
            description
        )
        VALUES (?, ?, ?)
        """,
        (
            alias,
            "ALIAS_ENABLED",
            f"Alias reactivated for {row['service']}."
        )
    )


    conn.commit()
    conn.close()


    return jsonify({

        "success": True,

        "message":
            "Alias enabled successfully."

    })


# ==================================================
# PRIVACY SIGNUP ANALYZER
# ==================================================

@app.route("/api/analyze-signup", methods=["POST"])
def analyze_signup():

    data = request.get_json() or {}


    # ----------------------------------------------
    # SERVICE
    # ----------------------------------------------

    service = data.get(
        "service",
        "Unknown Website"
    )

    service = str(service).strip()


    if not service:

        return jsonify({

            "error": "Service name is required."

        }), 400


    # ----------------------------------------------
    # INITIAL SCORE
    # ----------------------------------------------

    score = 0

    recommendations = []


    # ----------------------------------------------
    # EMAIL
    # ----------------------------------------------

    if data.get("email"):

        score += 10

        recommendations.append(
            "Use a unique privacy alias instead of your real email."
        )


    # ----------------------------------------------
    # FULL NAME
    # ----------------------------------------------

    if data.get("name"):

        score += 10

        recommendations.append(
            "Provide your real name only when required."
        )


    # ----------------------------------------------
    # PHONE
    # ----------------------------------------------

    if data.get("phone"):

        score += 15

        recommendations.append(
            "Avoid sharing your phone number unless necessary."
        )


    # ----------------------------------------------
    # ADDRESS
    # ----------------------------------------------

    if data.get("address"):

        score += 20

        recommendations.append(
            "Do not provide your address unless the service genuinely needs it."
        )


    # ----------------------------------------------
    # DATE OF BIRTH
    # ----------------------------------------------

    if data.get("dob"):

        score += 15

        recommendations.append(
            "Avoid sharing your date of birth unless required."
        )


    # ----------------------------------------------
    # LOCATION
    # ----------------------------------------------

    if data.get("location"):

        score += 15

        recommendations.append(
            "Avoid sharing location information unnecessarily."
        )


    # ----------------------------------------------
    # LIMIT SCORE
    # ----------------------------------------------

    score = min(
        score,
        100
    )


    # ----------------------------------------------
    # RISK LEVEL
    # ----------------------------------------------

    if score >= 70:

        risk_level = "HIGH"

    elif score >= 40:

        risk_level = "MEDIUM"

    else:

        risk_level = "LOW"


    # ----------------------------------------------
    # SUMMARY MESSAGE
    # ----------------------------------------------

    if risk_level == "HIGH":

        message = (
            "This service requests several types of "
            "personal information. Consider minimizing "
            "the information you provide."
        )

    elif risk_level == "MEDIUM":

        message = (
            "This service requests a moderate amount "
            "of personal information. Review which "
            "fields are actually necessary."
        )

    else:

        message = (
            "This service requests a relatively small "
            "amount of personal information."
        )


    # ----------------------------------------------
    # RETURN ANALYSIS
    # ----------------------------------------------

    return jsonify({

        "success": True,

        "service": service,

        "risk_score": score,

        "risk_level": risk_level,

        "message": message,

        "recommendations": recommendations

    })


# ==================================================
# APPLICATION START
# ==================================================

if __name__ == "__main__":

    app.run(debug=True)
