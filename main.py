from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_gravatar import Gravatar
from functools import wraps
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)

############### CONNECT TO DB ###############
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

############### CONFIGURE LOGIN ###############
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(user_id)

############### FUNCIÓN DECORADORA PARA ADMIN ###############
def admin_only(func):
    @wraps(func)        # Sin esto me arrojaba error, la verdad no sé el porque
    def decorated_function(*args, **kwargs):    # Recibe los parámetros de la función (si es que hay)
        if current_user.get_id() == "1":        # Comprobamos que él id sea el del admin
            return func(*args, **kwargs)        # Si si lo es avanzamos con la función
        return abort(403)                       # Si no, damos seguimiento
    return decorated_function


############### CONFIGURAR GRAVATAR PARA QUE PONGA IMAGENES A LAS CUENTAS ###############
# Lo unico relevante/importante es especificar la app, el tamaño y si acaso el 'default'
gravatar = Gravatar(app, size=30, default="retro", force_default=False, force_lower=False, base_url=None)

############### CONFIGURE TABLES ###############

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")

    def __repr__(self):
        return f"<Blog {self.title}>"


#############################################
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")

    def __repr__(self):
        return f"<User {self.email}>"


#############################################
class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    body = db.Column(db.String(500), nullable=False)


############### RUTAS DE LA PÁGINA WEB ###############
@app.route('/')
def get_all_posts():
    # posts = BlogPost.query.all()
    posts = db.session.query(BlogPost).all()
    return render_template("index.html", all_posts=posts, user=current_user)

@app.route("/crear")
def crear():
    db.create_all()
    return redirect(url_for("get_all_posts"))


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("Este correo ya ha sido registrado antes.")

        else:
            new_user = User()
            new_user.name = form.username.data
            new_user.email = form.email.data
            new_user.password = generate_password_hash(form.password.data)

            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form, user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Buscamos y comprobamos que exista el correo en la base de datos.
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Comprobamos la contraseña
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for("get_all_posts"))

            else:
                flash("Contraseña incorrecta.")         # Mensaje de seguimiento
        else:
            flash("Correo incorrecto o inexistente.")   # Mensaje de seguimiento
    return render_template("login.html", form=form, user=current_user)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    all_comments = db.session.query(Comment).filter_by(parent_post=requested_post).all()
    form = CommentForm()
    if form.validate_on_submit():
        new_comment = Comment(comment_author=current_user,
                              parent_post=requested_post,
                              body=form.comment.data)

        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("show_post", post_id=post_id))
    return render_template("post.html", form=form, user=current_user, post=requested_post, comments=all_comments)


@app.route("/about")
def about():
    return render_template("about.html", user=current_user)


@app.route("/contact")
def contact():
    return render_template("contact.html", user=current_user)


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, user=current_user)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, user=current_user)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    # app.run(host='0.0.0.0', port=5000, debug=True)
    app.run(debug=True)
