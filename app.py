import os
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

MODERATORS = {'mear','mr-zombii'}

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

            is_mod = session['username'].lower() in MODERATORS
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

    media_files = [f for f in all_files if not f.startswith('raw_') and not f.startswith('pending_') and (f.endswith('.mp4') or f.endswith('.gif') or f.endswith('.png') or f.endswith('.jpg') or f.endswith('.jpeg'))]
    media_files.sort(key=lambda x: os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], x)), reverse=True)


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
    bio_user = profile_view if profile_view else session['username']


    bio_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{bio_user}_bio.txt")

  
    if not os.path.exists(bio_path):
        for f in os.listdir(app.config['UPLOAD_FOLDER']):
            if f.lower() == f"{bio_user.lower()}_bio.txt":
                bio_path = os.path.join(app.config['UPLOAD_FOLDER'], f)
                break

    if os.path.exists(bio_path):
        with open(bio_path, "r", encoding="utf-8") as f:
            user_bio = f.read()

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
 
    pending_queue = []
    is_current_user_mod = session['username'].lower() in MODERATORS

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
        pending_queue=pending_queue
    ))

 
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'

  
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

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
    base_name = filename.rsplit('.', 1)[0]
    p = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_likes.txt")
    c = 0
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            try: c = int(f.read().strip())
            except ValueError: c = 0
    with open(p, "w", encoding="utf-8") as f:
        f.write(str(c + 1))
  
    creator_name = filename.split("_", 1)[0] if "_" in filename else None
    if creator_name and creator_name.lower() != session['username'].lower():
        add_notification(creator_name, f" @{session['username']} liked your clip ({base_name})!")

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
        add_notification(creator_name, f" @{session['username']} commented on your clip: \"{text[:20]}...\"")

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
        add_notification(target_username, f" @{session['username']} started following you!")

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
    if 'username' not in session or session['username'].lower() not in MODERATORS:
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
            add_notification(creator_name, f" Success! @{session['username']} approved your meme clip. It is now live on the public feed!")
        except Exception:
            pass

        flash('Meme verified as FUNNY and pushed live!')

    return redirect(url_for('feed'))

@app.route('/reject/<filename>', methods=['POST'])
def reject_meme(filename):
    if 'username' not in session or session['username'].lower() not in MODERATORS:
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
            add_notification(creator_name, f" Your uploaded clip was rejected by @{session['username']} for being UNFUNNY. Try harder next time!")
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
            if user_record['question'] and user_record['answer']:
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
        flash(" Incorrect security answer!")
    return render_template('2fa.html', question=user_record['question'] if user_record else "", username=username)

if __name__ == '__main__':
    app.run(debug=True)

