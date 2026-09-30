import os
import json
import queue
CHAT_LISTENERS = {}
from flask import Flask, render_template, request, redirect, url_for, flash, make_response, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)
app.secret_key = "google_giggles_ultra_secure_session_key"



UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'mp4', 'gif', 'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 150 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

USER_REGISTRY_FILE = os.path.join(os.path.dirname(__file__), "secure_users.txt")

MODERATORS_FILE = os.path.join(os.path.dirname(__file__), "secure_mods.txt")


def get_moderators_list():

    mods = {'mear'}
    if os.path.exists(MODERATORS_FILE):
        with open(MODERATORS_FILE, "r", encoding="utf-8") as f:
            for line in f:

                cleaned_line = line.strip().lower()
                if cleaned_line:
                    mods.add(cleaned_line)
    return mods



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def add_notification(target_user, alert_text):
    if not target_user:
        return
    notif_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{target_user.lower()}_notifications.txt")
    with open(notif_path, "a", encoding="utf-8") as f:
        f.write(alert_text + "\n")

def get_following_list(username):
    following_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{username.lower()}_following.txt")
    if not os.path.exists(following_path):
        return []
    with open(following_path, "r", encoding="utf-8") as f:
        return [line.strip().lower() for line in f.readlines() if line.strip()]

def find_user(username):
    if not os.path.exists(USER_REGISTRY_FILE):
        return None
    with open(USER_REGISTRY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("||")
            if parts[0].lower() == username.lower():
                return {
                    "username": parts[0],
                    "password": parts[1],
                    "question": parts[2] if len(parts) > 2 else None,
                    "answer": parts[3] if len(parts) > 3 else None
                }
    return None


@app.route('/', methods=['GET', 'POST'])
def feed():

    if 'username' not in session:
        return redirect(url_for('login_screen'))

    profile_view = request.args.get('profile', '').strip()

    search_query = request.args.get('q', '').strip().lower()

    if request.method == 'POST':
        if 'media_file' not in request.files:
            flash('No file component detected.')
            return redirect(request.url)

        file = request.files['media_file']
        caption_text = request.form.get('caption', '').strip()

        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)


            is_mod = session['username'].lower() in get_moderators_list()
            prefix = f"{session['username']}_" if is_mod else f"pending_{session['username']}_"


            unique_filename = f"{prefix}{filename}"
            final_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            if os.path.exists(final_path):
                name_part, ext_part = filename.rsplit('.', 1)
                counter = 1
                while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], f"{prefix}v{counter}_{name_part}.{ext_part}")):
                    counter += 1
                unique_filename = f"{prefix}v{counter}_{name_part}.{ext_part}"
                final_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            file.save(final_path)

            if caption_text:
                base_name = unique_filename.rsplit('.', 1)[0]
                caption_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_caption.txt")
                with open(caption_path, "w", encoding="utf-8") as f:
                    f.write(caption_text)


            if is_mod:
                flash('Meme posted live instantly by Chief Executive Officer Mear!')
            else:
                flash('Meme sent to the Mod Queue! Awaiting verification from @Mear to confirm it is actually funny.')

            return redirect(url_for('feed', profile=session['username']))


    matched_accounts = []
    if search_query and os.path.exists(USER_REGISTRY_FILE):
        with open(USER_REGISTRY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("||")
                if parts and search_query in parts[0].lower():
                    matched_accounts.append(parts[0])

    all_files = os.listdir(app.config['UPLOAD_FOLDER'])

    media_files = [f for f in all_files if not f.startswith('raw_') and not f.startswith('pending_') and not f.startswith('pfp_') and (f.endswith('.mp4') or f.endswith('.gif') or f.endswith('.png') or f.endswith('.jpg') or f.endswith('.jpeg'))]

    posts_data = []
    for filename in media_files:
        if "_" not in filename:
            continue

        base_name = filename.rsplit('.', 1)[0]
        likes_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_likes.txt")
        comments_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_comments.txt")
        caption_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_caption.txt")

        creator_tag = filename.split("_", 1)[0]

        if profile_view and creator_tag.lower() != profile_view.lower():
            continue

        caption = ""
        if os.path.exists(caption_path):
            with open(caption_path, "r", encoding="utf-8") as f:
                caption = f.read()

        if search_query and not profile_view:
            if search_query not in creator_tag.lower() and search_query not in caption.lower():
                continue

        like_count = 0
        if os.path.exists(likes_path):
            with open(likes_path, "r", encoding="utf-8") as f:
                try: like_count = int(f.read().strip())
                except ValueError: like_count = 0

        comments = []
        if os.path.exists(comments_path):
            with open(comments_path, "r", encoding="utf-8") as f:
                comments = [line.strip() for line in f.readlines() if line.strip()]

        posts_data.append({
            "filename": filename,
            "likes": like_count,
            "comments": comments,
            "creator": creator_tag,
            "caption": caption
        })

    user_bio = ""
    bio_user = profile_view if profile_view else session.get('username', '')

    bio_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{bio_user}_bio.txt")
    if not os.path.exists(bio_path):
        for f in os.listdir(app.config['UPLOAD_FOLDER']):
            if f.lower() == f"{bio_user.lower()}_bio.txt":
                bio_path = os.path.join(app.config['UPLOAD_FOLDER'], f)
                break

    if os.path.exists(bio_path):
        with open(bio_path, "r", encoding="utf-8") as f:
            user_bio = f.read()

    status_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{bio_user.lower()}_status_posts.txt")
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            for line in f:
                if "||" in line:
                    ts, content = line.strip().split("||", 1)
                    posts_data.append({
                        "filename": f"text_status_{ts}.txt",
                        "likes": 0,
                        "comments": [],
                        "creator": bio_user,
                        "caption": content,
                        "is_text_only": True
                    })

    import random
    random.shuffle(posts_data)

    current_following = get_following_list(session['username'])
    is_following_profile = profile_view.lower() in current_following if profile_view else False

    follower_count = 0
    if profile_view:
        for f in os.listdir(app.config['UPLOAD_FOLDER']):
            if f.endswith('_following.txt'):
                with open(os.path.join(app.config['UPLOAD_FOLDER'], f), "r", encoding="utf-8") as list_f:
                    if profile_view.lower() in [line.strip().lower() for line in list_f.readlines()]:
                        follower_count += 1

    notifications = []
    notif_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session['username'].lower()}_notifications.txt")
    if os.path.exists(notif_path):
        with open(notif_path, "r", encoding="utf-8") as f:
            notifications = [line.strip() for line in f.readlines() if line.strip()]
        notifications.reverse()

    is_target_profile_mod = profile_view.lower() in get_moderators_list() if profile_view else False

    target_pfp = None
    target_statuses = []
    for f in os.listdir(app.config['UPLOAD_FOLDER']):
        if f.startswith(f"pfp_{bio_user.lower()}."):
            target_pfp = f
            break

    target_status_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{bio_user.lower()}_status_posts.txt")
    if os.path.exists(target_status_path):
        with open(target_status_path, "r", encoding="utf-8") as f:
            for line in f:
                if "||" in line:
                    ts, content = line.strip().split("||", 1)
                    target_statuses.append({"timestamp": ts, "content": content})
        target_statuses.reverse()

    pending_queue = []
    is_current_user_mod = session['username'].lower() in get_moderators_list()

    if is_current_user_mod:
        for f in os.listdir(app.config['UPLOAD_FOLDER']):
            if f.startswith('pending_') and (f.endswith('.mp4') or f.endswith('.gif') or f.endswith('.png') or f.endswith('.jpg') or f.endswith('.jpeg')):
                try:
                    creator_name = f.split('_', 2)[1]
                except IndexError:
                    creator_name = "unknown"


                b_name = f.rsplit('.', 1)[0]
                cap_p = os.path.join(app.config['UPLOAD_FOLDER'], f"{b_name}_caption.txt")
                cap = ""
                if os.path.exists(cap_p):
                    with open(cap_p, "r", encoding="utf-8") as cap_f:
                        cap = cap_f.read()

                pending_queue.append({"filename": f, "creator": creator_name, "caption": cap})

    # ⚡ CHATROOM SCANNER: Maps active rooms inside the routing architecture context safely
    authorized_chatrooms = []
    for file in os.listdir(app.config['UPLOAD_FOLDER']):
        if file.endswith('_meta.txt'):
            c_room_id = file.replace('_meta.txt', '')
            try:
                with open(os.path.join(app.config['UPLOAD_FOLDER'], file), "r", encoding="utf-8") as f:
                    if session['username'].lower() in [line.strip().lower() for line in f]:
                        authorized_chatrooms.append(c_room_id)
            except: pass

    # ⚡ Ensure the word 'response' aligns perfectly here
    response = make_response(render_template(
        'feed.html',
        posts=posts_data,
        current_user=session['username'],
        profile_view=profile_view,
        user_bio=user_bio,
        search_query=search_query,
        matched_accounts=matched_accounts,
        is_following_profile=is_following_profile,
        follower_count=follower_count,
        notifications=notifications[:15],
        is_mod=is_current_user_mod,
        pending_queue=pending_queue,
        is_target_profile_mod=is_target_profile_mod,
        target_pfp=target_pfp,
        target_statuses=target_statuses,
        my_chats=authorized_chatrooms
    ))

    return response



@app.route('/update_bio', methods=['POST'])
def update_bio():
    if 'username' in session:
        bio_text = request.form.get('bio', '').strip()
        bio_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session['username']}_bio.txt")
        with open(bio_path, "w", encoding="utf-8") as f:
            f.write(bio_text)
    return redirect(url_for('feed', profile=session['username']))

@app.route('/delete/<filename>', methods=['POST'])
def delete_post(filename):
    if 'username' in session and filename.startswith(f"{session['username']}_"):
        base_name = filename.rsplit('.', 1)[0]
        paths = [
            os.path.join(app.config['UPLOAD_FOLDER'], filename),
            os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_likes.txt"),
            os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_comments.txt")
        ]
        for p in paths:
            if os.path.exists(p):
                os.remove(p)
        flash("Post removed successfully.")
        return redirect(url_for('feed', profile=session['username']))
    return redirect(url_for('feed'))



@app.route('/logout')
def logout_action():
    session.pop('username', None)
    return redirect(url_for('login_screen'))

@app.route('/like/<filename>', methods=['POST'])
def like_post(filename):
    if 'username' not in session:
        return redirect(url_for('login_screen'))

    base_name = filename.rsplit('.', 1)[0]
    likes_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_likes.txt")
    liked_users_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_liked_users.txt")


    already_liked = []
    if os.path.exists(liked_users_path):
        with open(liked_users_path, "r", encoding="utf-8") as f:
            already_liked = [line.strip().lower() for line in f.readlines() if line.strip()]

    current_user_lower = session['username'].lower()


    if current_user_lower in already_liked:
        flash("You have already verified this meme as funny!")
        return redirect(url_for('feed'))


    c = 0
    if os.path.exists(likes_path):
        with open(likes_path, "r", encoding="utf-8") as f:
            try: c = int(f.read().strip())
            except ValueError: c = 0


    with open(likes_path, "w", encoding="utf-8") as f:
        f.write(str(c + 1))


    with open(liked_users_path, "a", encoding="utf-8") as f:
        f.write(current_user_lower + "\n")

    creator_name = filename.split("_", 1)[0] if "_" in filename else None
    if creator_name and creator_name.lower() != session['username'].lower():
        add_notification(creator_name, f"❤️ @{session['username']} liked your clip ({base_name})!")

    return redirect(url_for('feed'))


@app.route('/comment/<filename>', methods=['POST'])
def add_comment(filename):
    text = request.form.get('comment', '').strip()
    if text and 'username' in session:

        base_name = filename.rsplit('.', 1)[0]
        p = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_comments.txt")
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"{session['username']}: {text}\n")

    creator_name = filename.split("_", 1)[0] if "_" in filename else None
    if creator_name and creator_name.lower() != session['username'].lower():
        add_notification(creator_name, f"💬 @{session['username']} commented on your clip: \"{text[:20]}...\"")

    return redirect(url_for('feed'))
@app.route('/follow/<target_username>', methods=['POST'])
def follow_user(target_username):
    if 'username' not in session or session['username'].lower() == target_username.lower():
        return redirect(url_for('feed'))

    following_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session['username'].lower()}_following.txt")
    current_following = get_following_list(session['username'])

    if target_username.lower() in current_following:
        current_following.remove(target_username.lower())
        with open(following_path, "w", encoding="utf-8") as f:
            for user in current_following:
                f.write(user + "\n")
    else:
        with open(following_path, "a", encoding="utf-8") as f:
            f.write(target_username.lower() + "\n")
        add_notification(target_username, f"👤 @{session['username']} started following you!")

    return redirect(url_for('feed', profile=target_username))

@app.route('/clear_notifications', methods=['POST'])
def clear_notifications():
    if 'username' in session:
        notif_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session['username'].lower()}_notifications.txt")
        if os.path.exists(notif_path):
            os.remove(notif_path)
    return redirect(url_for('feed'))

@app.route('/approve/<filename>', methods=['POST'])
def approve_meme(filename):
    if 'username' not in session or session['username'].lower() not in get_moderators_list():

        return redirect(url_for('feed'))

    if filename.startswith('pending_'):

        clean_name = filename.replace('pending_', '', 1)

        old_video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        new_video_path = os.path.join(app.config['UPLOAD_FOLDER'], clean_name)

        if os.path.exists(old_video_path):
            os.rename(old_video_path, new_video_path)


        old_base = filename.rsplit('.', 1)[0]
        new_base = clean_name.rsplit('.', 1)[0]

        old_cap = os.path.join(app.config['UPLOAD_FOLDER'], f"{old_base}_caption.txt")
        new_cap = os.path.join(app.config['UPLOAD_FOLDER'], f"{new_base}_caption.txt")

        if os.path.exists(old_cap):
            os.rename(old_cap, new_cap)


        try:
            creator_name = filename.split('_', 2)[1]
            add_notification(creator_name, f"🎉 Success! @{session['username']} approved your meme clip. It is now live on the public feed!")
        except Exception:
            pass

        flash('Meme verified as FUNNY and pushed live!')

    return redirect(url_for('feed'))


@app.route('/reject/<filename>', methods=['POST'])
def reject_meme(filename):
    if 'username' not in session or session['username'].lower() not in get_moderators_list():

        return redirect(url_for('feed'))

    if filename.startswith('pending_'):
        base_name = filename.rsplit('.', 1)[0]


        paths = [
            os.path.join(app.config['UPLOAD_FOLDER'], filename),
            os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_caption.txt")
        ]
        for p in paths:
            if os.path.exists(p):
                os.remove(p)
        try:
            creator_name = filename.split('_', 2)[1]
            add_notification(creator_name, f"❌ Your uploaded clip was rejected by @{session['username']} for being UNFUNNY. Try harder next time!")
        except Exception:
            pass


        flash('Unfunny post successfully dropped and deleted from storage.')

    return redirect(url_for('feed'))
@app.route('/register', methods=['GET', 'POST'])
def register_screen():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if find_user(username):
            flash("That username tag signature is already taken!")
            return redirect(url_for('register_screen'))


        hashed_password = generate_password_hash(password)
        hashed_answer = generate_password_hash(request.form.get('custom_answer', '').strip().lower())

        with open(USER_REGISTRY_FILE, "a", encoding="utf-8") as f:
            f.write(f"{username}||{hashed_password}||{request.form.get('custom_question', '').strip()}||{hashed_answer}\n")

        flash("Registration complete!")
        return redirect(url_for('login_screen'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login_screen():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user_record = find_user(username)

        if user_record and check_password_hash(user_record['password'], password):
            if user_record.get('question') and user_record.get('answer'):
                return redirect(url_for('two_factor_checkpoint', username=username))
            session['username'] = user_record['username']
            return redirect(url_for('feed'))

        flash("Invalid username or password credentials.")
    return render_template('login.html')

@app.route('/2fa/<username>', methods=['GET', 'POST'])
def two_factor_checkpoint(username):
    user_record = find_user(username)
    if request.method == 'POST' and user_record:
        user_answer = request.form.get('2fa_answer', '').strip().lower()

        if check_password_hash(user_record['answer'], user_answer):
            session['username'] = user_record['username']
            return redirect(url_for('feed'))
        flash("❌ Incorrect security answer!")
    return render_template('2fa.html', question=user_record['question'] if user_record else "", username=username)
@app.route('/toggle_mod/<target_username>', methods=['POST'])
def toggle_mod(target_username):

    if 'username' not in session or session['username'].lower() != 'mear':
        return redirect(url_for('feed'))

    if target_username.lower() == 'mear':
        return redirect(url_for('feed', profile=target_username))


    current_mods = set()
    if os.path.exists(MODERATORS_FILE):
        with open(MODERATORS_FILE, "r", encoding="utf-8") as f:
            current_mods = {line.strip().lower() for line in f if line.strip()}

    if target_username.lower() in current_mods:
        current_mods.remove(target_username.lower())
        add_notification(target_username, "⚠️ Your Moderator permissions have been revoked by @Mear.")
        flash(f"Moderator privileges revoked from @{target_username}")
    else:
        current_mods.add(target_username.lower())
        add_notification(target_username, "👑 Congratulations! @Mear has promoted you to an official Platform Moderator!")
        flash(f"@{target_username} successfully promoted to Moderator!")

    # Write clean state back to disk
    with open(MODERATORS_FILE, "w", encoding="utf-8") as f:
        for mod in current_mods:
            f.write(mod + "\n")

    return redirect(url_for('feed', profile=target_username))
@app.route('/upload_pfp', methods=['POST'])
def upload_pfp():
    if 'username' not in session:
        return redirect(url_for('login_screen'))

    if 'pfp_file' not in request.files:
        flash('No file component detected.')
        return redirect(url_for('feed', profile=session['username']))

    file = request.files['pfp_file']
    if file.filename == '':
        flash('No file selected.')
        return redirect(url_for('feed', profile=session['username']))

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        pfp_filename = f"pfp_{session['username'].lower()}.{ext}"
        final_path = os.path.join(app.config['UPLOAD_FOLDER'], pfp_filename)

        # Clean out any old profile pictures first
        for existing_file in os.listdir(app.config['UPLOAD_FOLDER']):
            if existing_file.startswith(f"pfp_{session['username'].lower()}."):
                try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], existing_file))
                except: pass

        file.save(final_path)
        flash('Profile picture updated successfully!')

    return redirect(url_for('feed', profile=session['username']))


@app.route('/post_status', methods=['POST'])
def post_status():
    if 'username' not in session:
        return redirect(url_for('login_screen'))

    status_text = request.form.get('status_content', '').strip()
    if status_text:
        status_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session['username'].lower()}_status_posts.txt")
        import time
        timestamp = int(time.time())
        with open(status_path, "a", encoding="utf-8") as f:
            f.write(f"{timestamp}||{status_text}\n")
        flash('Status posted successfully!')

    return redirect(url_for('feed', profile=session['username']))
@app.route('/create_chat', methods=['POST'])
def create_chat():
    if 'username' not in session: return redirect(url_for('login_screen'))

    import time
    room_id = f"room_{int(time.time())}"

    # ⚡ FIXED: Forces the path to save inside static/uploads/
    chat_meta_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{room_id}_meta.txt")

    with open(chat_meta_path, "w", encoding="utf-8") as f:
        f.write(f"{session['username'].lower()}\n")

    flash(f"Secure Chatroom initialized!")
    return redirect(url_for('chatroom_view', room_id=room_id))


@app.route('/chat/<room_id>', methods=['GET', 'POST'])
def chatroom_view(room_id):
    if 'username' not in session: return redirect(url_for('login_screen'))

    # ⚡ FIXED: Points safely to static/uploads/
    chat_meta_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{room_id}_meta.txt")

    authorized = False
    if os.path.exists(chat_meta_path):
        with open(chat_meta_path, "r", encoding="utf-8") as f:
            authorized = session['username'].lower() in [line.strip().lower() for line in f]

    if not authorized:
        flash("⛔ ACCESS DENIED!")
        return redirect(url_for('feed'))

    return render_template('chat.html', room_id=room_id, current_user=session['username'])


@app.route('/invite_to_chat/<room_id>', methods=['POST'])
def invite_to_chat(room_id):
    if 'username' not in session:
        return redirect(url_for('login_screen'))

    target_user = request.form.get('target_username', '').strip().lower()

    if target_user and find_user(target_user):
        # 🚀 TRANSMIT INVITE: Drops a clean, unescaped clickable hyperlink into their dashboard timeline metrics
        add_notification(target_user, f"✉️ @{session['username']} invited you to join an elite group chat! <a href='/accept_chat/{room_id}' style='color:#34a853;font-weight:bold;text-decoration:underline;'>[JOIN]</a>")
        flash(f"Invitation cleanly transmitted over the grid to @{target_user}!")
    else:
        flash("Could not discover that username signature on the registry grid.")

    return redirect(url_for('chatroom_view', room_id=room_id))

@app.route('/accept_chat/<room_id>')
def accept_chat(room_id):
    if 'username' not in session: return redirect(url_for('login_screen'))
    chat_meta_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{room_id}_meta.txt")

    if os.path.exists(chat_meta_path):
        # Securely append their username signature to the access authorization file
        with open(chat_meta_path, "a", encoding="utf-8") as f:
            f.write(f"{session['username'].lower()}\n")
        flash("You have successfully authorized your terminal and joined the chatroom!")
        return redirect(url_for('chatroom_view', room_id=room_id))

    flash("This chat environment has expired or does not exist.")
    return redirect(url_for('feed'))


@app.route('/leave_chat/<room_id>', methods=['POST'])
def leave_chat(room_id):
    if 'username' not in session: return redirect(url_for('login_screen'))
    chat_meta_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{room_id}_meta.txt")

    if os.path.exists(chat_meta_path):
        with open(chat_meta_path, "r", encoding="utf-8") as f:
            members = [line.strip().lower() for line in f if line.strip()]
        if session['username'].lower() in members:
            members.remove(session['username'].lower())
        # Write remaining members back or kill room file entirely if empty
        if members:
            with open(chat_meta_path, "w", encoding="utf-8") as f:
                for m in members: f.write(f"{m}\n")
        else:
            try: os.remove(chat_meta_path)
            except: pass

    flash("You left the chatroom panel securely.")
    return redirect(url_for('feed'))


@app.route('/chat_send/<room_id>', methods=['POST'])
def chat_send(room_id):
    if 'username' not in session: return ("Unauthorized", 401)
    msg_text = request.form.get('message', '').strip()

    if msg_text:
        chat_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{room_id}_chat.txt")
        # ⚡ ACCESSIBLE FILE STORAGE: Saves messages permanently to disk
        with open(chat_path, "a", encoding="utf-8") as f:
            f.write(f"{session['username']}||{msg_text}\n")

    return ("", 204)


@app.route('/chat_messages/<room_id>')
def chat_messages(room_id):
    if 'username' not in session: return ("Unauthorized", 401)
    chat_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{room_id}_chat.txt")

    messages = []
    if os.path.exists(chat_path):
        with open(chat_path, "r", encoding="utf-8") as f:
            for line in f:
                if "||" in line:
                    user, msg = line.strip().split("||", 1)
                    messages.append({"user": user, "msg": msg})

    return {"messages": messages}

if __name__ == '__main__':
    app.run(debug=True)
