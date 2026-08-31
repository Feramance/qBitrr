"""Contract and policy tests for the deterministic GitHub classifier."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "classify_work_item.py"
SPEC = importlib.util.spec_from_file_location("classifier", SCRIPT)
assert SPEC and SPEC.loader
classifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(classifier)
POLICY = json.loads(
    (Path(__file__).parents[2] / "automation" / "classification-policy.json").read_text()
)


def pull(title: str, author: str = "human", body: str = "", head: str = "topic") -> dict:
    return {
        "number": 10,
        "title": title,
        "body": body,
        "user": {"login": author, "type": "Bot" if author.endswith("[bot]") else "User"},
        "base": {"ref": "master", "sha": "b" * 40, "repo": {"full_name": "o/r"}},
        "head": {"ref": head, "sha": "h" * 40, "repo": {"full_name": "o/r"}},
    }


def changed(*paths: str) -> list[dict]:
    return [
        {"filename": path, "status": "modified", "additions": 1, "deletions": 1} for path in paths
    ]


class DigestTests(unittest.TestCase):
    def test_shared_vector(self) -> None:
        vector = {"z": [3, {"b": True, "a": "é"}], "a": None}
        self.assertEqual(
            classifier.digest(vector),
            "37783aa0d31ee16e06aa5432d54c8154c68d52e69871b399a1fc6d0d0d0538cd",
        )

    def test_contract_round_trip(self) -> None:
        value = {"schema_version": 1, "category": "docs", "flags": []}
        self.assertEqual(classifier.decode_contract(classifier.encode_contract(value)), value)

    def test_automation_labels_do_not_change_digest(self) -> None:
        self.assertEqual(
            classifier.non_automation_labels(
                ["bug", "automation/type:bug", "codex/bug", "n8n/waiting-ci"]
            ),
            ["bug"],
        )

    def test_current_base_sha_encodes_branch_ref(self) -> None:
        class RecordingAPI:
            def __init__(self) -> None:
                self.calls = []

            def request(self, method: str, path: str, payload=None):
                self.calls.append((method, path, payload))
                return {"object": {"sha": "c" * 40}}

        api = RecordingAPI()
        value = classifier.current_base_sha(api, {"base": {"ref": "release/v1"}})
        self.assertEqual(value, "c" * 40)
        self.assertEqual(api.calls, [("GET", "/git/ref/heads/release%2Fv1", None)])


class LabelProvisioningTests(unittest.TestCase):
    def test_classification_labels_replace_stale_managed_labels(self) -> None:
        class RecordingAPI:
            def __init__(self) -> None:
                self.calls = []

            def request(self, method: str, path: str, payload=None):
                self.calls.append((method, path, payload))
                return None

        api = RecordingAPI()
        classifier.update_classification_labels(
            api,
            42,
            [
                "bug",
                "automation/classification:pending",
                "automation/type:ci",
                "automation/type:ambiguous",
            ],
            "docs",
            True,
        )
        self.assertEqual(
            api.calls,
            [
                (
                    "PUT",
                    "/issues/42/labels",
                    {
                        "labels": [
                            "automation/classification:ready",
                            "automation/type:docs",
                            "bug",
                        ]
                    },
                )
            ],
        )

    def test_concurrent_create_converges_to_patch(self) -> None:
        class RacingAPI:
            def __init__(self) -> None:
                self.calls = []
                self.raced = False

            def pages(self, _path: str) -> list:
                return []

            def request(self, method: str, path: str, payload=None):
                self.calls.append((method, path, payload))
                if method == "POST" and not self.raced:
                    self.raced = True
                    raise classifier.GitHubAPIError(
                        method,
                        "https://api.github.test/labels",
                        422,
                        '{"errors":[{"code":"already_exists"}]}',
                    )
                return None

        api = RacingAPI()
        classifier.ensure_labels(api)
        self.assertEqual(api.calls[0][0], "POST")
        self.assertEqual(api.calls[1][0], "PATCH")

    def test_non_conflict_create_failure_is_not_hidden(self) -> None:
        class FailingAPI:
            def pages(self, _path: str) -> list:
                return []

            def request(self, method: str, _path: str, payload=None):
                raise classifier.GitHubAPIError(method, "https://api.github.test", 403, "denied")

        with self.assertRaises(classifier.GitHubAPIError):
            classifier.ensure_labels(FailingAPI())


class IssueTests(unittest.TestCase):
    def issue(self, title: str, body: str, labels: list[str]) -> dict:
        return {"number": 1, "title": title, "body": body, "labels": [{"name": x} for x in labels]}

    def test_issue_forms(self) -> None:
        cases = [
            ("bug", "Steps to reproduce", ["bug"]),
            ("feature", "Proposed solution", ["enhancement"]),
            ("docs", "Documentation request", ["documentation"]),
            ("support", "Support request", ["question"]),
        ]
        for expected, body, labels in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    classifier.classify_issue(self.issue("x", body, labels))[0], expected
                )

    def test_repository_change_categories(self) -> None:
        for rendered, expected in [
            ("Refactor", "refactor"),
            ("Test", "test"),
            ("CI", "ci"),
            ("Maintenance", "maintenance"),
            ("Process change", "process_change"),
            ("Other", "other"),
        ]:
            body = f"### Requested change category\n\n{rendered}\n"
            self.assertEqual(classifier.classify_issue(self.issue("x", body, []))[0], expected)

    def test_conflict_is_ambiguous_and_override_wins(self) -> None:
        issue = self.issue("x", "", ["bug", "enhancement"])
        self.assertEqual(classifier.classify_issue(issue)[0], "ambiguous")
        self.assertEqual(classifier.classify_issue(issue, "feature")[0], "feature")


class LinkedIssueTests(unittest.TestCase):
    def test_bare_release_note_references_are_ignored(self) -> None:
        body = "Release notes\n- upstream change (#10995)\n- see owner/project#1298"
        self.assertEqual(classifier.linked_issue_numbers("bump package", body, 10), [])

    def test_explicit_link_keywords_are_supported(self) -> None:
        body = "Fixes #12 and #13\nRelated to: #14\nRefs #10"
        self.assertEqual(classifier.linked_issue_numbers("change", body, 10), [12, 13, 14])

    def test_missing_local_issue_is_not_fatal(self) -> None:
        class MissingAPI:
            def request(self, method: str, path: str):
                raise classifier.GitHubAPIError(method, path, 404, "not found")

        self.assertIsNone(classifier.current_issue_classification(MissingAPI(), 999))


class PullRequestTests(unittest.TestCase):
    def classify(self, value: dict, files: list[dict], labels=(), links=(), override=None) -> str:
        return classifier.classify_pr(value, files, labels, links, POLICY, override)[0]

    def test_trusted_dependency_bots(self) -> None:
        for bot in ("dependabot[bot]", "pre-commit-ci[bot]"):
            self.assertEqual(
                self.classify(pull("bump", bot), changed("webui/package-lock.json")),
                "package_update",
            )

    def test_human_dependency_needs_label(self) -> None:
        files = changed(".pre-commit-config.yaml")
        self.assertEqual(self.classify(pull("bump"), files), "ambiguous")
        self.assertEqual(self.classify(pull("bump"), files, ["dependencies"]), "package_update")

    def test_workflow_action_version_bump_is_package_update(self) -> None:
        files = changed(".github/workflows/ci.yml")
        files[0]["patch"] = "@@ -1 +1 @@\n- uses: actions/checkout@v4\n+ uses: actions/checkout@v5"
        self.assertEqual(
            self.classify(pull("bump checkout", "dependabot[bot]"), files),
            "package_update",
        )

    def test_broad_workflow_edit_is_not_package_update(self) -> None:
        files = changed(".github/workflows/ci.yml", "webui/package-lock.json")
        files[0]["patch"] = "@@ -1 +1 @@\n- permissions: read-all\n+ permissions: write-all"
        self.assertNotEqual(
            self.classify(pull("bump", "dependabot[bot]"), files),
            "package_update",
        )

    def test_exclusive_paths(self) -> None:
        self.assertEqual(self.classify(pull("update"), changed("docs/index.md")), "docs")
        self.assertEqual(self.classify(pull("update"), changed("tests/test_a.py")), "test")
        self.assertEqual(self.classify(pull("update"), changed(".github/workflows/ci.yml")), "ci")

    def test_title_only_fix_is_ambiguous(self) -> None:
        self.assertEqual(self.classify(pull("fix: claim"), changed("qBitrr/main.py")), "ambiguous")

    def test_linked_bug_and_feature(self) -> None:
        files = changed("qBitrr/main.py")
        self.assertEqual(
            self.classify(pull("x"), files, links=[{"number": 1, "category": "bug"}]), "bug_fix"
        )
        self.assertEqual(
            self.classify(pull("x"), files, links=[{"number": 1, "category": "feature"}]),
            "feature",
        )

    def test_managed_handoff_requires_all_signals(self) -> None:
        value = pull(
            "x",
            POLICY["managed_app_bot_login"],
            "<!-- codex-issue-pr --> Fixes #1",
            "codex/issue-1-automated-fix",
        )
        self.assertEqual(
            self.classify(
                value, changed("qBitrr/main.py"), links=[{"number": 1, "category": "bug"}]
            ),
            "bug_fix",
        )

    def test_flags(self) -> None:
        value = pull("feat!: change", POLICY["managed_app_bot_login"])
        value["head"]["repo"]["full_name"] = "fork/r"
        files = changed(".github/workflows/ci.yml", "docs/assets/openapi.json")
        flags = classifier.determine_flags(value, files, POLICY, value["title"])
        for expected in (
            "breaking_change",
            "workflow_permissions_change",
            "generated_code",
            "public_api_change",
            "managed_n8n_app",
            "fork_head",
        ):
            self.assertIn(expected, flags)


if __name__ == "__main__":
    unittest.main()
