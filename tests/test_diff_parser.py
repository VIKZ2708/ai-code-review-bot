from reviewer.diff_parser import annotate_patch

PATCH = """@@ -1,3 +1,4 @@
 import os
-x = 1
+x = 2
+y = 3
 print(x)
\\ No newline at end of file"""


def test_added_lines_tracked_with_new_numbers():
    text, added = annotate_patch(PATCH)
    assert added == {2, 3}
    assert "    2 + x = 2" in text
    assert "    4   print(x)" in text
    assert "      - x = 1" in text


def test_multiple_hunks_reset_line_numbers():
    patch = "@@ -1,1 +1,2 @@\n a\n+b\n@@ -50,1 +51,2 @@\n c\n+d"
    _, added = annotate_patch(patch)
    assert added == {2, 52}
