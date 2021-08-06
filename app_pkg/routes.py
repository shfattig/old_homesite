from flask import render_template, flash, redirect, url_for, request, send_from_directory
from app_pkg import app, db, socketio
from app_pkg.forms import LoginForm, RegistrationForm, AddItemForm, ItemListForm, UserForm, SaveImageForm
from flask_login import current_user, login_user, logout_user, login_required
from app_pkg.models import User, Item, Comment, Drawing, DrawingNode, Description, DescriptionNode
from werkzeug.urls import url_parse
from threading import Lock
from flask_socketio import emit
from sqlalchemy import exc
import json
from base64 import b64encode, b64decode
import os

##### Initializations #####
thread = None
thread_lock = Lock()


class ItemState:
    def __init__(self):
        self.editing_comment = False


class StateManager:
    def __init__(self, item_id_list):
        self.edit_comment_just_pressed = False
        self.item_states = {}  # dict to hold state information
        for item_id in item_id_list:
            self.item_states[item_id] = ItemState()

try:
    my_state_manager = StateManager([item.id for item in db.session.query(Item).all()])
except exc.SQLAlchemyError:
    pass


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    # Initialize forms
    add_item_form = AddItemForm()
    item_list_form = ItemListForm()

    # Load all items from database
    item_list = db.session.query(Item).all()

    # TODO: Remove?
    if my_state_manager.edit_comment_just_pressed:
        my_state_manager.edit_comment_just_pressed = False
        for item in item_list:
            if my_state_manager.item_states[item.id].editing_comment:
                item_list_form.comment.data = item.comment
                break

    # Adding new item
    if add_item_form.add_item.data and add_item_form.validate_on_submit():
        print("Adding item <{}>...".format(add_item_form.item_input.data))
        item = Item(name=add_item_form.item_input.data, requestor=current_user)
        db.session.add(item)
        db.session.commit()
        my_state_manager.item_states[item.id] = ItemState()
        return redirect(url_for('index'))

    # Submitting new comment
    elif item_list_form.submit_comment.data and item_list_form.validate_on_submit():
        print("Submitting comment...")
        for item in db.session.query(Item).all():
            if my_state_manager.item_states[item.id].editing_comment:
                item.comment = item_list_form.comment.data
                db.session.commit()
                my_state_manager.item_states[item.id].editing_comment = False
        return redirect(url_for('index'))

    # Clearing selections
    elif item_list_form.clear_selected.data:
        print("Clearing items...")
        print(request.form)
        for item in item_list:
            if request.form.get(str(item.id)):
                print("Deleted {}".format(item.id))
                print(item.comments == db.session.query(Comment).filter_by(item_id=item.id).all())
                for comment in item.comments:
                    print("Deleting comment: " + comment.text)
                    db.session.delete(comment)
                print("Deleting item: " + item.name)
                db.session.delete(item)
        db.session.commit()
        return redirect(url_for('index'))

    # Clear all items
    elif item_list_form.clear_all.data:
        print("Clearing all items...")
        for item in item_list:
            db.session.delete(item)
            del my_state_manager.item_states[item.id]
        db.session.commit()
        return redirect(url_for('index'))
    try:
        permissions = db.session.query(User).filter_by(username=current_user.username).first().permissions
    except AttributeError:
        permissions = 100 # high number means no permissions
    return render_homesite_page('index.html', title="Home", add_form=add_item_form, list_form=item_list_form, item_list=item_list, item_states=my_state_manager.item_states)

@socketio.on('delete_comment', namespace='/groceries')
def delete_comment(message):
    comment = db.session.query(Comment).filter_by(id=message['comment_id']).first()
    print("Deleting comment: " + comment.text)
    db.session.delete(comment)
    db.session.commit()

@socketio.on('add_item', namespace='/groceries')
def add_item(message):
    # Create item, then add item and commit to db session
    item = Item(name=message['data'], requestor=current_user)
    db.session.add(item)
    db.session.commit()

    # Initialize comment editing status
    my_state_manager.item_states[item.id] = ItemState()

    # Emit signal to viewer for update
    socketio.emit('add_item',
                  {'item_id': item.id, 'item_name': item.name, 'username': current_user.username, 'comment': ''},
                      namespace='/groceries')

def render_homesite_page(url, errors=[], **kwargs):
    try:
        permissions = db.session.query(User).filter_by(username=current_user.username).first().permissions
    except AttributeError:
        permissions = 100 # high number means no permissions
    return render_template(url, permissions=permissions, errors=errors, **kwargs)

@app.route('/draw', methods=['GET', 'POST'])
@app.route('/draw/<description_id>', methods=['GET', 'POST'])
@login_required
def draw(description_id=None, errors=[]):
    description = db.session.query(Description).filter_by(id=description_id).first()
    if description is None:
        desc_text = None
    else:
        desc_text = description.text
    return render_homesite_page('canvas.html', description=desc_text, desc_id=description_id) #json.dumps(description_id))

@app.route('/retrieve_image_names', methods=['GET', 'POST'])
def retrieve_image_names():
    image_list = [image.name for image in db.session.query(Drawing).all()]
    return image_list

@app.route('/retrieve_descs', methods=['GET', 'POST'])
def retrieve_descs():
    desc_list = [(desc.id, desc.text) for desc in db.session.query(Description).all()]
    return desc_list

def find_image(filename):
    print("Searching for file: " + filename)
    image_list = db.session.query(Drawing).filter_by(name=filename).all()
    if len(image_list) == 0:
        print("No image found...")
        return None
    else:
        print("Image found!")
        if len(image_list) > 1:
            print("WARNING: Found multiple images named: {}".format(filename))
        return image_list[0]

def delete_image(image_name):
    image = find_image(image_name)
    if image is None:
        return 1
    else:
        drawing_node = db.session.query(DrawingNode).filter_by(drawing_id=image.id).first()
        db.session.delete(drawing_node)

        description_node = db.session.query(DescriptionNode).filter_by(prev_drawing_id =image.id).first()
        db.session.delete(description_node)

        description_node = db.session.query(DescriptionNode).filter_by(next_drawing_id=image.id).first()
        db.session.delete(description_node)

        db.session.delete(image)
        db.session.commit()

        os.remove(f"app_pkg/static/{image.image_data}")
        return 0


@app.route('/load_file', methods=['GET', 'POST'])
def load_file():
    filename = request.form['filename']
    image = db.session.query(Drawing).filter_by(name=filename).first()
    if image is not None:
        drawing_node = db.session.query(DrawingNode).filter_by(drawing_id=image.id).first()
        ## TEMP ##
        if drawing_node is None:
            drawing_node = DrawingNode(drawing_id=image.id)
            db.session.add(drawing_node)
        ## TEMP ##
        prev_description = db.session.query(Description).filter_by(id=drawing_node.prev_desc_id).first()
        next_description = db.session.query(Description).filter_by(id=drawing_node.next_desc_id).first()
        if prev_description is None:
            p_desc_text = None
        else:
            p_desc_text = prev_description.text
        if next_description is None:
            n_desc_text = None
        else:
            n_desc_text = next_description.text
        image_data = get_image_data(image.image_data)

        return json.dumps({'img_data':image_data, 'prev_description':p_desc_text, 'next_description':n_desc_text})
    else:
        return json.dumps({'img_data':None})

@app.route('/delete_file', methods=['GET', 'POST'])
def delete_file():
    filename = request.form['filename']
    err = delete_image(filename)
    if err:
        return "Could not find {}".format(filename)
    else:
        return "Removed {}".format(filename)

@app.route('/select_image', methods=['GET', 'POST'])
def select_image():
    filename = request.form['filename']
    print('Running select image for filename: ' + filename)
    return url_for('write_description') + '/' + filename

@app.route('/game_start', methods=['GET', 'POST'])
def game_start():
    return render_homesite_page('game_start.html')

def get_drawing_endpoints():
    image_ids = [image_node.drawing_id for image_node in db.session.query(DrawingNode).all() if image_node.next_desc_id is None]
    image_list = [image.name for image in db.session.query(Drawing).filter(Drawing.id.in_(image_ids)).all()]
    return image_list

def get_desc_endpoints():
    desc_ids = [desc_node.desc_id for desc_node in db.session.query(DescriptionNode).all() if desc_node.next_drawing_id is None]
    desc_list = [(desc.id, desc.text) for desc in db.session.query(Description).filter(Description.id.in_(desc_ids)).all()]
    return desc_list

@app.route('/pick_drawing', methods=['GET', 'POST'])
def pick_drawing():
    return render_homesite_page('pick_drawing.html', image_list=get_drawing_endpoints())

@app.route('/pick_description', methods=['GET', 'POST'])
def pick_description():
    return render_homesite_page('pick_description.html', desc_list=get_desc_endpoints())

@app.route('/delete_desc', methods=['GET', 'POST'])
def delete_desc():
    desc_id = request.form['id']
    desc = db.session.query(Description).filter_by(id=desc_id).first()
    db.session.delete(desc)
    db.session.commit()
    return "Removed desc {}".format(desc_id)

@app.route('/select_desc', methods=['GET', 'POST'])
def select_desc():
    description_id = request.form['id']
    return url_for('draw') + '/' + description_id

@app.route('/first_description', methods=['GET'])
def first_description():
    description = db.session.query(Description).first()
    if description is not None:
        return json.dumps({'text': description.text, 'id': description.id})
    # No descriptions
    return json.dumps({'text': "None", 'id': 0})

@app.route('/prev_description', methods=['GET'])
def prev_description():
    description_id = int(request.args.get('id'))
    description_list = db.session.query(Description).all()
    for i, desc in enumerate(description_list):
        if desc.id == description_id:
            description = description_list[(i - 1) % len(description_list)]
            return json.dumps({'text': description.text, 'id': description.id})
    # No descriptions
    return json.dumps({'text': "None", 'id': 0})

@app.route('/next_description', methods=['GET'])
def next_description():
    description_id = int(request.args.get('id'))
    description_list = db.session.query(Description).all()
    for i, desc in enumerate(description_list):
        if desc.id == description_id:
            description = description_list[(i + 1) % len(description_list)]
            return json.dumps({'text': description.text, 'id': description.id})
    # No descriptions
    return json.dumps({'text': "None", 'id': 0})

@app.route('/write_description/<filename>', methods=['POST'])
@app.route('/write_description', methods=['POST'])
def description_post(filename=None):
    description_text = request.form['description_text']

    new_description = Description(text=description_text, user_id=current_user.id)
    db.session.add(new_description)
    db.session.flush()
    db.session.refresh(new_description)

    if filename is None:
        image_id = None
    else:
        image = find_image(filename)
        if image is None:
            image_id = None
        else:
            image_id = image.id
    new_description_node = DescriptionNode(desc_id=new_description.id, prev_drawing_id=image_id)

    drawing_node = db.session.query(DrawingNode).filter_by(drawing_id=image_id).first()
    if drawing_node is not None:
        drawing_node.next_desc_id = new_description.id
    db.session.add(new_description_node)

    db.session.commit()
    return submitted()

def get_image_data(filepath):
    """ Retrieve image file from filesystem and prepare for displaying on web
    """
    return f"/static/{filepath}"
    f = open(filepath, 'rb')
    image_data = f.read()
    image_data = b64encode(image_data)
    print(type(image_data))
    image_data = image_data.replace(b"+", b" ")
    image_data = b"data:image/png;base64," + image_data
    return image_data

@app.route('/write_description/<filename>', methods=['GET'])
@app.route('/write_description', methods=['GET'])
def write_description(filename=None):
    image_name = "None"
    image_data = None
    if filename is not None:
        image_name = filename
        image = find_image(filename)
        if image is not None:
            image_data = get_image_data(image.image_data)
    return render_homesite_page('description.html', image_name=image_name, image_data=image_data)

@app.route('/submitted', methods=['GET'])
def submitted():
    return render_homesite_page('submitted.html')

@app.route('/gallery', methods=['GET'])
def visit_gallery():
    return render_homesite_page('gallery.html', gallery_sequences=[1, 2, 3, 4])

@app.route('/save', methods=['GET', 'POST'])
@login_required
def save():

    # Get filename from form
    filename = request.form['save_fname'] + '.png'

    # If filename given
    if filename != "":
        # Not used yet
        data = request.form['save_cdata']

        canvas_image = request.form['save_image']

        # Write image to file
        filepath = f"images/{filename}"
        with open(f"app_pkg/static/{filepath}", 'wb+') as f:
            png_filedata = canvas_image.replace("data:image/png;base64,", "")
            png_filedata = png_filedata.replace(" ", "+")
            png_filedata = b64decode(png_filedata)
            f.write(png_filedata)

        # If new filename, save image data to database
        if len(db.session.query(Drawing).filter_by(name=filename).all()) == 0:
            new_drawing = Drawing(name=filename, user_id=current_user.id, image_data=filepath)
            db.session.add(new_drawing)
            db.session.flush()
            db.session.refresh(new_drawing)

            desc_id = request.form['desc_id']
            if desc_id == "":
                desc_id = None
            new_drawing_node = DrawingNode(drawing_id=new_drawing.id, prev_desc_id=desc_id)
            description_node = db.session.query(DescriptionNode).filter_by(desc_id=desc_id).first()
            if description_node is not None:
                description_node.next_drawing_id = new_drawing.id
            db.session.add(new_drawing_node)

            db.session.commit()
            return "No errors"
        # Overwrite old file
        else:
            drawing = db.session.query(Drawing).filter_by(name=filename).first()
            drawing.image_data = filepath
            drawing.user_id = current_user.id
            db.session.commit()
            return "Overwrote old file: {}".format(filename)
    else:
        return "ERROR: No filename"

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
        return render_homesite_page('users.html', title="Home", form=user_form, user_list=user_list)

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
    return render_homesite_page('login.html', title='Sign In', form=form)


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
    return render_homesite_page('register.html', title='Register', form=form)


@socketio.on('new_comment', namespace='/groceries')
def init_comment(message):
    item_id = message['item_id']

    # Get item from db
    item = db.session.query(Item).filter_by(id=item_id).first()

    # Create new comment and add to db
    curr_comment = Comment(text='', item=item)
    db.session.add(curr_comment)
    db.session.commit()

    # Tell viewer the id of the new comment
    socketio.emit('new_comment',
                  {'item_id': item_id, 'comment_id': curr_comment.id},
                  namespace='/groceries')

@socketio.on('submit_comment', namespace='/groceries')
def submit_comment(message):
    print("Submitting comment...")
    comment_id = message['comment_id']
    text = message['data']

    curr_comment = db.session.query(Comment).filter_by(id=comment_id).first()
    curr_comment.text = text
    db.session.commit()
    socketio.emit('submit_comment',
                  {'comment_id': curr_comment.id, 'comment': text},
                  namespace='/groceries')


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


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while False:
        socketio.sleep(1)
        count += 1
        socketio.emit('my_response',
                      {'data': 'Server generated event', 'count': count},
                      namespace='/test')
        if current_user:
            username = current_user.username
        else:
            username = 'boobooface'
        socketio.emit('add_item',
                      {'item_id': 4, 'item_name': 'Server generated event', 'username': username, 'comment': 'yo dog'},
                      namespace='/groceries')


@socketio.on('connect', namespace='/test')
def test_connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(background_thread)
    emit('my_response', {'data': 'Connected', 'count': 30})


@socketio.on('disconnect', namespace='/test')
def test_disconnect():
    print('Client disconnected', request.sid)

