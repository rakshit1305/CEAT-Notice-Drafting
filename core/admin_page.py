"""The admin page: who can sign in to the console.

There is no self-signup. An admin adds a person here with a temporary password,
passes it on, and the person is made to replace it the first time they sign in.
Everything destructive is guarded in core/auth.py — an admin cannot lock
themselves out, and the last active admin cannot be removed — so this file only
has to show what auth.py says.
"""
from __future__ import annotations

import streamlit as st

from . import auth as AUTH
from . import store as STORE
from .uikit import fit


def _when(v) -> str:
    return f"{v.astimezone():%d.%m.%Y %H:%M}" if v else "—"


def _flash() -> None:
    msg = st.session_state.pop("_admin_flash", None)
    if msg:
        (st.success if msg[0] == "ok" else st.error)(msg[1])


def _done(text: str) -> None:
    st.session_state["_admin_flash"] = ("ok", text)
    st.rerun()


def render(me: dict) -> None:
    st.markdown("## Users")
    st.caption("Everyone who can sign in to the Notice Drafting Console. Admins can open "
               "this page; users can only draft.")
    _flash()

    users = AUTH.list_users()
    st.dataframe(
        [{"Email": u["email"],
          "Role": u["role"],
          "Status": "active" if u["is_active"] else "deactivated",
          "Password": "temporary — must change" if u["must_change_password"] else "set by them",
          "Last sign-in": _when(u["last_login_at"]),
          "Added": _when(u["created_at"])} for u in users],
        hide_index=True, **fit("dataframe"))

    add, manage = st.columns(2, gap="large")

    # ---------------------------------------------------------------- add --
    with add:
        with st.container(border=True, key="glass_admin_add"):
            st.markdown("**Add a person**")
            with st.form("admin_add", clear_on_submit=True):
                email = st.text_input("Email — what they sign in with",
                                      placeholder="name@ceat.com")
                role = st.radio("Role", AUTH.ROLES, index=1, horizontal=True,
                                format_func=lambda r: {"admin": "Admin — can manage users",
                                                       "user": "User — drafting only"}[r])
                pw = st.text_input("Temporary password", type="password",
                                   help="Leave it blank and one is generated for you.")
                go = st.form_submit_button("Create the account", type="primary",
                                           **fit("form_submit_button"))
            if go:
                generated = not pw
                pw = pw or AUTH.temp_password()
                try:
                    u = AUTH.create_user(email, pw, role)
                except AUTH.AuthError as e:
                    st.error(str(e))
                else:
                    _done(f"{u['email']} can now sign in"
                          + (f" with the temporary password `{pw}` — pass it on; it is not "
                             "shown again." if generated else " with the password you set.")
                          + " They will be asked to choose their own on first sign-in.")

    # ------------------------------------------------------------- manage --
    with manage:
        with st.container(border=True, key="glass_admin_manage"):
            st.markdown("**Change an account**")
            by_id = {u["id"]: u for u in users}
            uid = st.selectbox("Account", list(by_id), key="admin_pick",
                               format_func=lambda i: by_id[i]["email"]
                               + ("  ·  you" if i == me["id"] else ""))
            u = by_id[uid]
            # Keyed by the account, so picking another one rebuilds the boxes
            # instead of carrying the last person's settings across.
            with st.form(f"admin_edit_{uid}"):
                role = st.radio("Role", AUTH.ROLES, index=AUTH.ROLES.index(u["role"]),
                                horizontal=True)
                active = st.checkbox("Can sign in", value=u["is_active"])
                pw = st.text_input("New temporary password", type="password",
                                   help="Leave blank to keep their password. Setting one signs "
                                        "them out everywhere and makes them choose a new one.")
                save = st.form_submit_button("Save changes", type="primary",
                                             **fit("form_submit_button"))
            if save:
                try:
                    AUTH.set_role(uid, role, acting_id=me["id"])
                    if active != u["is_active"]:
                        AUTH.set_active(uid, active, acting_id=me["id"])
                    if pw:
                        AUTH.reset_password(uid, pw)
                except AUTH.AuthError as e:
                    st.error(str(e))
                else:
                    _done(f"Saved {u['email']}.")

            with st.expander("Delete this account"):
                st.caption("Deactivating (untick “Can sign in”) is usually what you want: it "
                           "can be undone. Deleting removes the account; the matters and "
                           "notices they made stay, without their name.")
                sure = st.checkbox(f"Yes, delete {u['email']}", key=f"admin_sure_{uid}")
                if st.button("Delete the account", key=f"admin_del_{uid}", disabled=not sure,
                             **fit("button")):
                    try:
                        AUTH.delete_user(uid, acting_id=me["id"])
                    except AUTH.AuthError as e:
                        st.error(str(e))
                    else:
                        _done(f"Deleted {u['email']}.")

    # -------------------------------------------------------------- usage --
    with st.expander("Model usage — last 30 days"):
        usage = STORE.llm_usage(30)
        if not usage:
            st.caption("No model calls recorded yet.")
        else:
            st.dataframe(
                [{"Who": r["who"], "Calls": r["calls"], "Tokens in": int(r["tokens_in"]),
                  "Tokens out": int(r["tokens_out"]), "Last call": _when(r["last_call"])}
                 for r in usage], hide_index=True, **fit("dataframe"))
