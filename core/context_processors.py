from django.urls import reverse


def workspace_navigation(request):
    user = request.user
    route = request.resolver_match.url_name if request.resolver_match else ""
    if not user.is_authenticated or route in {"home", "login", "logout"}:
        return {}

    roles = set(user.groups.values_list("name", flat=True))
    admin = user.is_superuser or "admin" in roles
    teacher = "teacher" in roles
    items = [("dashboard", "Tổng quan", "▦", "overview")]
    if admin or teacher:
        items += [
            ("question_bank", "Ngân hàng câu hỏi", "?", "questions"),
            ("blueprint_bank", "Cấu hình đề thi", "▤", "blueprints"),
            ("rubric_bank", "Thang điểm", "≡", "rubrics"),
        ]
    if admin:
        items.append(("demo_accounts", "Tài khoản", "◎", "accounts"))
    if "student" in roles and not (admin or teacher):
        items[0] = ("dashboard", "Học phần và luyện tập", "▦", "overview")

    section = "overview"
    for prefix, key in (("question_", "questions"), ("blueprint_", "blueprints"),
                        ("rubric_", "rubrics"), ("demo_account", "accounts")):
        if route.startswith(prefix):
            section = key
            break
    nav = [{"url": reverse(name), "label": label, "icon": icon,
            "active": key == section} for name, label, icon, key in items]
    parent = next((item for item in items if item[3] == section), items[0])
    is_root = route == parent[0] or route.startswith("dashboard")
    back_route = "dashboard" if is_root else parent[0]
    back_label = "Tổng quan" if is_root else parent[1]
    return {"workspace_nav": nav, "workspace_role": "Quản trị viên" if admin else (
        "Giảng viên" if teacher else "Sinh viên"), "workspace_section": parent[1],
        "workspace_back_url": reverse(back_route), "workspace_back_label": back_label,
        "workspace_show_back": not is_root,
        "workspace_show_section": section != "overview",
        "workspace_is_detail": not is_root}
