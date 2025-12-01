import streamlit as st
from datetime import datetime
import time
import sqlite3
import uuid, re, os, base64, io
from io import BytesIO
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_core.messages import HumanMessage, AIMessage
from streamlit_option_menu import option_menu
from langgraph_backend import chatbot
from auth.signup import show_signup_dialog
from auth.signin import show_signin_dialog
from user_profile.view_profile import show_view_profile_dialog
from user_profile.edit_profile import show_edit_profile_dialog
from user_profile.change_password import show_change_password_dialog
from data_base.database import (
    get_thread_list,
    create_thread,
    set_thread_title,
    load_messages,
    append_message,
    delete_thread,
    conn,
)
from multimodel import text_to_image, image_to_text, pil_to_b64
from PIL import Image

st.set_page_config(page_title="Gemix AI")
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def is_guest_mode():
    return not st.session_state.get("logged_in", False)


def if_logged_in(func, *args, **kwargs):
    if not is_guest_mode():
        return func(*args, **kwargs)

def trigger_dialog(flag_key: str):
    if st.session_state.get(flag_key):
        del st.session_state[flag_key]  
        return True
    return False


# Guest in-memory storage
if is_guest_mode() and "guest_messages" not in st.session_state:
    st.session_state.guest_messages = []


def init_session():
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "title_generated": False,
        "confirm_delete": None,
        "chat_search": "",
        "current_view": "chat",
        "last_thread": None,
        "guest_messages": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session()


def download_image(img_pil: Image.Image, prefix: str = "Gemix AI"):
    buf = BytesIO()
    img_pil.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"

    st.download_button(
        label="Download Image",
        data=buf.getvalue(),
        file_name=filename,
        mime="image/png",
        use_container_width=True,
        type="primary",
    )


def thread_belongs_to_user(thread_id: str, user_id: int) -> bool:
    """Return True if the thread really belongs to the logged-in user."""
    if not thread_id or is_guest_mode():
        return True
    cur = conn.execute(
        "SELECT 1 FROM threads WHERE thread_id = ? AND user_id = ?",
        (thread_id, user_id),
    )
    return cur.fetchone() is not None


def generate_title(conv):
    transcript = "\n".join(
        f"{'You' if m['role']=='user' else 'Assistant'}: {m['content']}"
        for m in conv[:6]
    )
    prompt = f"Return ONE title (3–6 words). Capitalize. No quotes.\nConversation:\n{transcript}\nTitle:"
    if GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            resp = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3, max_output_tokens=15
                ),
            )
            title = re.sub(r"[^\w\s]", "", resp.text.strip())
            title = " ".join(title.split()[:6]).capitalize()
            return title if len(title) > 3 else "New Chat"
        except:
            pass
    user_msg = next((m["content"] for m in conv if m["role"] == "user"), "")
    title = " ".join(user_msg.split()[:6]).capitalize()
    return (title[:50] + "..." if len(title) > 50 else title) or "New Chat"


def _msg_count(tid: str) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) FROM thread_messages WHERE thread_id = ?", (tid,)
    )
    return cur.fetchone()[0]


# CSS: Gradient Only | Big Main Title | Clean Sidebar
st.markdown(
    """
<style>
/* MAIN PAGE: Big Gradient Title (No Glow/Shadow) */
.main-novachat-title {
    font-family: 'Montserrat', 'Arial Black', sans-serif;
    font-weight: 900;
    font-size: 1000px;
    text-align: center;
    letter-spacing: 4px;
    background: linear-gradient(90deg,
        #00d4ff, #4d79ff, #7c3aed, #e91e63, #ff1744
    );
    background-size: 300% 300%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: gradientFlow 6s ease infinite;
    margin: 20px 0;
}
/* SIDEBAR: Normal Size, No Shadow/Glow */
.sidebar-novachat-title {
    font-family: 'Montserrat', sans-serif;
    font-weight: 700;
    font-size: 40px;
    text-align: center;
    background: linear-gradient(90deg, #00d4ff, #ff1744);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin:  0;
}
/* Gradient Animation */
@keyframes gradientFlow {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
/* Delete button subtle hover */
.del-btn:hover {
    transform: scale(1.15);
    transition: 0.2s;
}
</style>
""",
    unsafe_allow_html=True,
)


st.sidebar.markdown(
    '<h1 class="sidebar-GEMIX AI-title" >GEMIX AI</h1>', unsafe_allow_html=True
)
if not st.session_state.get("logged_in", False):
    with st.sidebar:
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "Sign Up",
                use_container_width=True,
                icon=":material/person_add:",
                type="primary",
            ):
                show_signup_dialog()

        with col2:
            if st.button(
                "Login",
                use_container_width=True,
                icon=":material/login:",
                type="primary",
            ):
                show_signin_dialog()

        st.markdown("---")
        st.caption("Sign in to save your history")

# Stop execution here if not logged in
user = st.session_state.get("user")
user_id = user.get("id") if user else None  # make sure your signin sets 'id'
username = user.get("username") if user else None
first_name = user.get("first_name") if user else None


# === FIXED USER & THREAD LOGIC ===
# ==================== FINAL WORKING USER & THREAD LOGIC ====================
if is_guest_mode():
    # ───── GUEST MODE ─────
    username = "Guest"
    user_id = "guest"  # we don’t need a UUID

    # One single in-memory thread for the whole guest session
    if "thread_id" not in st.session_state or not st.session_state.thread_id:
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.guest_messages = []  # reset messages

    current_thread_id = st.session_state.thread_id

else:
    # ───── LOGGED-IN USER ─────
    user = st.session_state.user
    user_id = user["id"]
    username = user.get("username", "User")
    first_name = user.get("first_name", "") or ""

    # If we are coming from a guest thread OR the current thread does NOT belong to this user → start fresh
    needs_new_thread = (
        "thread_id" not in st.session_state
        or
        # first time after login
        not st.session_state.thread_id
        or st.session_state.thread_id.startswith("guest_")
        or not thread_belongs_to_user(st.session_state.thread_id, user_id)
    )

    if needs_new_thread:
        new_thread_id = str(uuid.uuid4())
        create_thread(new_thread_id, user_id, "New Chat")
        st.session_state.thread_id = new_thread_id
        st.session_state.title_generated = False
        # IMPORTANT: clear any leftover guest messages so they don’t appear after login
        st.session_state.guest_messages = []

    current_thread_id = st.session_state.thread_id

if not is_guest_mode():
    with st.sidebar:
        st.success(f"Logged in as **{username}**")
        with st.expander(
            "My Account",
            icon=":material/person:",
        ):
            if st.button(
                "View Profile",
                use_container_width=True,
                type="secondary",
                icon=":material/visibility:",
            ):
                show_view_profile_dialog()

            if st.button(
                "Edit Profile",
                use_container_width=True,
                type="secondary",
                icon=":material/edit:",
            ):
                show_edit_profile_dialog()

            if st.button(
                "Change Password",
                use_container_width=True,
                type="secondary",
                icon=":material/lock_reset:",
            ):
                show_change_password_dialog()

            if st.button(
                "Logout",
                use_container_width=True,
                type="secondary",
                icon=":material/logout:",
            ):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()


if st.sidebar.button(
    "New Chat",
    use_container_width=True,
    key="new_chat",
    type="primary",
    icon=":material/chat_add_on:",
):
    new_id = str(uuid.uuid4())
    create_thread(new_id, user_id, "New Chat")
    st.session_state.thread_id = new_id
    st.session_state.title_generated = False
    st.session_state.confirm_delete = None
    st.session_state.chat_search = ""
    if_logged_in(create_thread, new_id, user_id, "New Chat")
    if is_guest_mode():
        st.session_state.guest_messages = []
    st.rerun()

st.sidebar.markdown("---")
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = "Chat"
# )
MODES = ["Chat", "GENERATE IMAGE", "GENERATE CAPTION"]

MODE = st.sidebar.pills(
    "Mode",
    options=MODES,
    default=st.session_state.selected_mode,
    key="mode_selector",
    width="stretch",
)


# Update session state when user changes mode
if MODE != st.session_state.selected_mode:
    st.session_state.selected_mode = MODE
    st.rerun()  # Optional: immediate switch

MODE = st.session_state.selected_mode
st.sidebar.markdown("---")
st.sidebar.header("My Chats")

all_threads = [] if is_guest_mode() else get_thread_list(user_id)

search_query = st.sidebar.text_input(
    "",
    value=st.session_state.chat_search,
    placeholder="Search your chats...",
    key="chat_search_input",
    label_visibility="collapsed",
)
if st.session_state.chat_search_input != st.session_state.chat_search:
    st.session_state.chat_search = st.session_state.chat_search_input


filtered_threads = [
    th
    for th in all_threads
    if _msg_count(th["thread_id"]) > 0
    and (not search_query or search_query.lower() in th["title"].lower())
]

if filtered_threads:
    st.sidebar.caption(
        f"{len(filtered_threads)} chat{'s' if len(filtered_threads) != 1 else ''}"
    )

    # SIDEBAR – Chat List (Filtered)
    for th in filtered_threads:
        col1, col2 = st.sidebar.columns([7, 1])
        with col1:
            if st.button(
                th["title"],
                key=f"btn_{th['thread_id']}",
                use_container_width=True,
                type="tertiary",
            ):
                st.session_state.thread_id = th["thread_id"]
                st.session_state.title_generated = True
                st.session_state.confirm_delete = None
                st.rerun()
        with col2:

            if st.button(
                "",
                key=f"del_{th['thread_id']}",
                help="Delete this chat",
                type="tertiary",
                icon=":material/delete:",
            ):
                st.session_state.confirm_delete = th["thread_id"]
                st.rerun()


elif is_guest_mode():
    st.sidebar.info("Guest Chat\nHistory not saved")
else:
    st.sidebar.info("No chats yet. Start a new one!")


if _msg_count(current_thread_id) == 0:
    st.markdown('<h1 class="main-GEMIX AI-title">GEMIX AI</h1>', unsafe_allow_html=True)
    if not is_guest_mode():
        st.markdown(
            f'<h2 class="main-GEMIX AI-title">Hi {first_name.capitalize()}</h2>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<h1 class="main-Gemix AI-title" >What’s on your mind today?</h1>',
        unsafe_allow_html=True,
    )
else:
    st.markdown("<br>", unsafe_allow_html=True)


# Main Chat Area
CONFIG = {"configurable": {"thread_id": current_thread_id}}

if (
    "cached_msgs" not in st.session_state
    or st.session_state.get("last_thread") != current_thread_id
):
    st.session_state.cached_msgs = (
        st.session_state.guest_messages
        if is_guest_mode()
        else load_messages(current_thread_id)
    )
    st.session_state.last_thread = current_thread_id

for i, msg in enumerate(st.session_state.cached_msgs):
    with st.chat_message(msg["role"]):
        if msg.get("content"):
            st.markdown(msg["content"])
        if msg.get("media_b64"):
            img_data = base64.b64decode(msg["media_b64"])
            img = Image.open(io.BytesIO(img_data))
            st.image(img, use_container_width=True)
            if st.button(
                "", key=f"save_hist_{i}_{current_thread_id}", icon=":material/save_alt:"
            ):
                download_image(img, prefix="chat_image")

# Delete Confirmation (above input)
if st.session_state.confirm_delete and not is_guest_mode():
    tid = st.session_state.confirm_delete
    title = next(
        (t["title"] for t in get_thread_list(user_id) if t["thread_id"] == tid),
        "this chat",
    )

    @st.dialog("Confirm Delete", width="small", on_dismiss="ignore")
    def delete_dialog_body(tid):

        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button(
                "Yes, Delete", type="primary", key="confirm_yes", width="stretch"
            ):
                delete_thread(tid)
                if st.session_state.thread_id == tid:
                    new_id = str(uuid.uuid4())
                    create_thread(new_id, user_id)
                    st.session_state.thread_id = new_id
                    st.session_state.title_generated = False
                st.session_state.confirm_delete = None
                st.rerun()
        with col_no:
            if st.button("Cancel", key="confirm_no", width="stretch"):
                st.session_state.confirm_delete = None
                st.rerun()

    delete_dialog_body(tid)
# Chat Input
if st.session_state.selected_mode == "Chat":
    if prompt := st.chat_input("Ask anything..."):

        append_message(current_thread_id, "user", prompt)
        st.session_state.cached_msgs.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        if not st.session_state.title_generated:
            title = generate_title(st.session_state.cached_msgs)
            set_thread_title(current_thread_id, title)
            st.session_state.title_generated = True

        with st.chat_message("assistant"):
            thinking = st.empty()
            thinking.markdown("*Thinking...*")

            typewriter = st.empty()

            full_response = ""

            try:
                for chunk in chatbot.stream(
                    {"messages": [HumanMessage(content=prompt)]},
                    config=CONFIG,
                    stream_mode="messages",
                ):
                    if not chunk:
                        continue

                    msg_chunk = chunk[0][0] if isinstance(chunk[0], tuple) else chunk[0]

                    if getattr(msg_chunk, "content", None):
                        delta = msg_chunk.content
                        full_response += delta
                        typewriter.markdown(full_response + "▋")

            except Exception as e:
                st.error(f"Chat error: {e}")
                full_response = "Sorry, something went wrong."

            finally:
                thinking.empty()

            append_message(current_thread_id, "assistant", full_response)
            st.session_state.cached_msgs.append(
                {"role": "assistant", "content": full_response}
            )

            if full_response.strip():
                for i in range(len(full_response) + 1):
                    typewriter.markdown(full_response[:i] + "▋")
                    time.sleep(0.005)
                typewriter.markdown(full_response)

        st.rerun()


elif st.session_state.selected_mode == "GENERATE IMAGE":
    st.subheader("Generate Image from Text")
    img_prompt = st.text_area("Describe the image", height=100)
    if st.button("Generate Image", type="primary", width="stretch"):
        with st.spinner("Creating image...", show_time=True):
            try:
                img = text_to_image(img_prompt)
                b64 = pil_to_b64(img)
                with st.chat_message("assistant"):
                    st.image(img, caption="Generated Image", use_container_width=True)
                    if st.button("Save This Image", key="save_txt2img"):
                        download_image(img, prefix="generated")
                append_message(current_thread_id, "user", img_prompt)
                append_message(
                    current_thread_id,
                    "assistant",
                    "Here's your generated image:",
                    media_b64=b64,
                )
                st.session_state.cached_msgs = load_messages(current_thread_id)
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

# MODE: Image to Text
elif st.session_state.selected_mode == "GENERATE CAPTION":
    st.subheader("Upload → Get Caption ")
    uploaded = st.file_uploader("Any image", type=["png", "jpg", "jpeg"])

    if uploaded:
        img = Image.open(uploaded).convert("RGB")
        st.image(img, use_container_width=True)

        if "image_caption" in st.session_state:
            st.code(st.session_state.image_caption)

        if st.button("Generate Caption", type="primary", width="stretch"):
            with st.spinner("Thinking..."):
                caption = image_to_text(img)

                st.session_state.image_caption = caption
                st.session_state.cached_msgs = load_messages(current_thread_id)
                append_message(current_thread_id, "user", "[Image]")
                append_message(current_thread_id, "assistant", caption)

            st.rerun()

if not is_guest_mode() and "guest_messages" in st.session_state:
    st.session_state.guest_messages = []
