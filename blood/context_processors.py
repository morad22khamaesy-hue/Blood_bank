# blood/context_processors.py
def user_role(request):
    role = ""
    try:
        if request.user.is_authenticated and hasattr(request.user, "profile"):
            role = request.user.profile.role
    except Exception:
        role = ""
    return {"user_role": role}
