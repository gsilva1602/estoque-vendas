from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import select

from ..decorators import roles_required
from ..extensions import db
from ..models import ROLES, User

bp = Blueprint("usuarios", __name__)


@bp.route("/usuarios", methods=["GET", "POST"])
@roles_required("admin")
def index():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip().lower()
        if not username or len(password) < 8 or role not in ROLES:
            flash("Informe usuário, senha com pelo menos 8 caracteres e perfil válido.", "error")
            return redirect(url_for("usuarios.index"))
        if db.session.scalar(select(User).where(User.username == username)):
            flash("Esse nome de usuário já existe.", "error")
            return redirect(url_for("usuarios.index"))
        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f"Usuário '{username}' criado.", "success")
        return redirect(url_for("usuarios.index"))
    users = db.session.scalars(select(User).order_by(User.username)).all()
    return render_template("usuarios.html", users=users)
