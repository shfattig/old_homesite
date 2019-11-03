from flask import render_template, flash, redirect, url_for, request
from app import app, db
from app.forms import LoginForm, RegistrationForm, AddItemForm, ItemListForm, UserForm
from flask_login import current_user, login_user, logout_user, login_required
from app.models import User, Item
from werkzeug.urls import url_parse


class ItemState:
    def __init__(self):
        self.editing_comment = False


class StateManager:
    def __init__(self, item_id_list):
        self.edit_comment_just_pressed = False
        self.item_states = {}  # dict to hold state information
        for item_id in item_id_list:
            self.item_states[item_id] = ItemState()


my_state_manager = StateManager([item.id for item in db.session.query(Item).all()])


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    add_item_form = AddItemForm()
    item_list_form = ItemListForm()
    item_list = db.session.query(Item).all()
    if my_state_manager.edit_comment_just_pressed:
        my_state_manager.edit_comment_just_pressed = False
        for item in item_list:
            if my_state_manager.item_states[item.id].editing_comment:
                item_list_form.comment.data = item.comment
                break
    if add_item_form.add_item.data and add_item_form.validate_on_submit():
        print("Adding item <{}>...".format(add_item_form.item_input.data))
        item = Item(name=add_item_form.item_input.data, requestor=current_user)
        db.session.add(item)
        db.session.commit()
        my_state_manager.item_states[item.id] = ItemState()
        return redirect(url_for('index'))
    elif item_list_form.submit_comment.data and item_list_form.validate_on_submit():
        print("Submitting comment...")
        for item in db.session.query(Item).all():
            if my_state_manager.item_states[item.id].editing_comment:
                item.comment = item_list_form.comment.data
                db.session.commit()
                my_state_manager.item_states[item.id].editing_comment = False
        return redirect(url_for('index'))
    elif item_list_form.clear_selected.data:
        print("Clearing items...")
        for item in item_list:
            if request.form.get(str(item.id)):
                print("Deleted {}".format(item.id))
                db.session.delete(item)
        db.session.commit()
        return redirect(url_for('index'))
    elif item_list_form.clear_all.data:
        print("Clearing all items...")
        for item in item_list:
            db.session.delete(item)
            del my_state_manager.item_states[item.id]
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('index.html', title="Home", add_form=add_item_form, list_form=item_list_form, item_list=item_list, item_states=my_state_manager.item_states, permissions=db.session.query(User).filter_by(username=current_user.username).first().permissions)


@app.route('/users', methods=['GET', 'POST'])
@login_required
def users():
    # Only admin can access this page
    if db.session.query(User).filter_by(username=current_user.username).first().permissions == 0:
        user_list = db.session.query(User).all()
        user_form = UserForm()
        if user_form.validate_on_submit():
            print("Registering submission")
            if user_form.new_user.data:
                print("Adding new user...")
                return redirect(url_for('new_user'))
            elif user_form.clear_selected.data:
                print("Clearing user...")
                delete_current_user = False
                for user in user_list:
                    if request.form.get(user.username):
                        if current_user.username == user.username:
                            delete_current_user = True
                        db.session.delete(user)
                        db.session.commit()
                        print("Deleted {}".format(user.username))
                if delete_current_user:
                    # pass on admin rights
                    new_admin = db.session.query(User).first()
                    print(new_admin)
                    if new_admin:
                        new_admin.permissions = 0
                        db.session.commit()
                    return redirect(url_for('logout'))
                else:
                    return redirect(url_for('users'))
            elif user_form.clear_all.data:
                print("Clearing all users...")
                for user in user_list:
                    db.session.delete(user)
                db.session.commit()
                return redirect(url_for('logout'))
        return render_template('users.html', title="Home", form=user_form, user_list=user_list, permissions=db.session.query(User).filter_by(username=current_user.username).first().permissions)
    else:
        flash('You do not have the proper permissions')
        return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    # prevent re-login
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form, permissions=1)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/new_user', methods=['GET', 'POST'])
def new_user():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        if len(db.session.query(User).all()) == 0:
            user.permissions = 0  # Setup automatic admin
        else:
            user.permissions = 1  # User privileges
        db.session.add(user)
        db.session.commit()
        if not current_user.is_authenticated:
            flash('Congratulations, you are now a registered user!')
            return redirect(url_for('login'))
        else:
            return redirect(url_for('users'))
    try:
        permissions = db.session.query(User).filter_by(username=current_user.username).first().permissions
    except AttributeError:
        permissions = 100 # high number means no permissions
    return render_template('register.html', title='Register', form=form, permissions=permissions)


@app.route('/edit_comment', methods=['GET', 'POST'])
def edit_comment():
    my_state_manager.edit_comment_just_pressed = True
    item_id = int(request.args.get('item_id'))
    my_state_manager.item_states[item_id].editing_comment = True
    # field = ItemListForm(request.form).comment
    # field.data = str(db.session.query(Item).filter_by(id=item_id).first().comment)
    # print(str(db.session.query(Item).filter_by(id=item_id).first().comment))
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    else:
        return redirect(url_for('new_user'))
