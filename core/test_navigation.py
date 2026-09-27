from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


class WorkspaceNavigationTests(TestCase):
    def login_role(self, role):
        user = get_user_model().objects.create_user(username=f"nav-{role}")
        user.groups.add(Group.objects.get_or_create(name=role)[0])
        self.client.force_login(user)

    def test_admin_navigation_persists_on_question_form(self):
        self.login_role("admin")
        response = self.client.get(reverse("question_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Chức năng"')
        self.assertContains(response, reverse("demo_accounts"))
        self.assertEqual(response.context["workspace_back_url"], reverse("question_bank"))
        self.assertContains(response, "← Về ngân hàng câu hỏi")
        active = [item["label"] for item in response.context["workspace_nav"] if item["active"]]
        self.assertEqual(active, ["Ngân hàng câu hỏi"])

    def test_catalogs_do_not_duplicate_sidebar_navigation(self):
        self.login_role("admin")
        for name in ("question_bank", "rubric_bank", "blueprint_bank", "demo_accounts"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'class="workspace-back"')
                self.assertNotContains(response, "Quay lại tổng quan")
                self.assertEqual(sum(item["active"] for item in response.context["workspace_nav"]), 1)

    def test_teacher_does_not_see_account_management(self):
        self.login_role("teacher")
        response = self.client.get(reverse("question_bank"))
        self.assertNotContains(response, reverse("demo_accounts"))
        self.assertContains(response, reverse("rubric_bank"))

    def test_student_navigation_and_public_login(self):
        self.login_role("student")
        response = self.client.get(reverse("dashboard_student"))
        self.assertContains(response, "Học phần và luyện tập")
        self.assertNotContains(response, reverse("question_bank"))
        self.client.logout()
        response = self.client.get(reverse("login"))
        self.assertNotContains(response, 'class="app-sidebar"')
