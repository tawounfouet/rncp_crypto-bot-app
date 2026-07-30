#!/usr/bin/env python3
"""
Genere un rapport de tests lisible (TXT) a partir du rapport JUnit XML de pytest.

Usage:
    python parse_test_report.py <xml_file> <txt_file>
    python parse_test_report.py  # utilise les chemins par defaut
"""

import os
import sys
import tempfile
from datetime import UTC, datetime

import defusedxml.ElementTree as ET


def parse_and_report(xml_file, txt_file):
    """Parse le rapport JUnit XML et genere un rapport TXT lisible."""

    if not os.path.exists(xml_file):
        print(f"[ERR] Fichier XML introuvable: {xml_file}")
        return False

    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Collecter les resultats par module
    modules_dict = {}
    summary = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}

    for suite in root.iter("testsuite"):
        if suite.tag == "testsuites":
            continue

        suite_name = suite.get("name", "unknown")

        # Extraire le nom du module depuis le classname pytest
        # ex: "tests.unit.test_health" → "test_health"
        module_name = suite_name.rsplit(".", 1)[-1] if "." in suite_name else suite_name

        if module_name not in modules_dict:
            modules_dict[module_name] = {
                "name": module_name,
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "tests": [],
            }

        mod = modules_dict[module_name]
        mod["total"] += int(suite.get("tests", 0))
        mod["failed"] += int(suite.get("failures", 0))
        mod["errors"] += int(suite.get("errors", 0))
        mod["skipped"] += int(suite.get("skipped", 0))

        for tc in suite.findall("testcase"):
            classname = tc.get("classname", "")
            name = tc.get("name", "")

            failure = tc.find("failure")
            error = tc.find("error")
            skipped_el = tc.find("skipped")

            if failure is not None:
                status = "FAILED"
                tb = (failure.text or "").strip()
            elif error is not None:
                status = "ERROR"
                tb = (error.text or "").strip()
            elif skipped_el is not None:
                status = "SKIPPED"
                tb = skipped_el.get("message", "")
            else:
                status = "PASSED"
                tb = ""

            mod["tests"].append(
                {"name": f"{name} ({classname})", "status": status, "traceback": tb}
            )

    # Finaliser et trier
    modules = []
    for module_name in sorted(modules_dict.keys()):
        mod = modules_dict[module_name]
        mod["passed"] = mod["total"] - mod["failed"] - mod["errors"] - mod["skipped"]
        mod["tests"].sort(key=lambda x: x["name"])
        modules.append(mod)

        summary["total"] += mod["total"]
        summary["passed"] += mod["passed"]
        summary["failed"] += mod["failed"]
        summary["errors"] += mod["errors"]
        summary["skipped"] += mod["skipped"]

    summary["success_rate"] = (
        round(summary["passed"] / summary["total"] * 100, 1)
        if summary["total"] > 0
        else 0
    )

    # Generer le TXT
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    s = summary

    lines = [
        "=" * 70,
        "RAPPORT DE TESTS CRYPTO-BOT",
        "=" * 70,
        f"Date: {timestamp}",
        f"Modules: {len(modules)}",
        "",
        "-" * 70,
        "RESUME",
        "-" * 70,
        f"Total:         {s['total']}",
        f"Passes:        {s['passed']}",
        f"Echoues:       {s['failed']}",
        f"Erreurs:       {s['errors']}",
        f"Skippes:       {s['skipped']}",
        f"Taux succes:   {s['success_rate']}%",
        "",
    ]

    for mod in modules:
        status = "OK" if mod["failed"] == 0 and mod["errors"] == 0 else "FAIL"
        lines.extend(
            [
                "-" * 70,
                f"MODULE: {mod['name']}  [{status}]",
                f"        {mod['passed']}/{mod['total']} passes",
                "-" * 70,
            ]
        )

        for test in mod["tests"]:
            icon = {
                "PASSED": "[OK]",
                "FAILED": "[FAIL]",
                "ERROR": "[ERR]",
                "SKIPPED": "[SKIP]",
            }.get(test["status"], "[?]")
            lines.append(f"  {icon:8} {test['name']}")

            if test["status"] in ("FAILED", "ERROR") and test["traceback"]:
                for tb_line in test["traceback"].split("\n")[:20]:
                    lines.append(f"           {tb_line}")
                lines.append("")

        lines.append("")

    lines.extend(["=" * 70, f"Rapport genere le {timestamp}", "=" * 70])

    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  Rapport TXT: {txt_file}")
    print(
        f"  {s['total']} tests | {s['passed']} passes | "
        f"{s['failed']} echoues | {s['errors']} erreurs | {s['success_rate']}%"
    )
    return s["failed"] == 0 and s["errors"] == 0


if __name__ == "__main__":
    if len(sys.argv) == 3:
        xml_path, txt_path = sys.argv[1], sys.argv[2]
    else:
        default_dir = os.path.join(tempfile.gettempdir(), "test-results")
        xml_path = os.path.join(default_dir, "report.xml")
        txt_path = os.path.join(default_dir, "test_report.txt")

    success = parse_and_report(xml_path, txt_path)
    sys.exit(0 if success else 1)
