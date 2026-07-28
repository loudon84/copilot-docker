from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from workcopilot_expert_factory import __version__
from workcopilot_expert_factory.builders.bundle import build_expert_bundle
from workcopilot_expert_factory.errors import ExpertFactoryError
from workcopilot_expert_factory.services.batch import select_experts
from workcopilot_expert_factory.services.bind_check import bind_check
from workcopilot_expert_factory.services.create import create_expert, customize_expert
from workcopilot_expert_factory.validators.expert import validate_expert

app = typer.Typer(
    name="expert",
    help="WorkCopilot Expert Factory CLI",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _print_report(report_dict: dict, fmt: str) -> None:
    if fmt in {"json", "both"}:
        console.print_json(data=report_dict)
    if fmt in {"text", "both"}:
        status = "PASSED" if report_dict.get("passed") else "FAILED"
        console.print(f"[bold]{status}[/bold]  {report_dict.get('expert_path')}")
        if report_dict.get("legacy"):
            console.print("[yellow]legacy mode[/yellow]")
        table = Table("level", "code", "path", "message")
        for issue in report_dict.get("issues") or []:
            table.add_row(issue["level"], issue["code"], issue.get("path") or "", issue["message"])
        if report_dict.get("issues"):
            console.print(table)


def _resolve_targets(
    path: Optional[Path],
    all_experts: bool,
    changed: bool,
) -> list[Path]:
    if all_experts or changed:
        targets = select_experts(all_experts=all_experts, changed=changed)
        if not targets:
            console.print("[yellow]no matching v1 experts[/yellow]")
        return targets
    if path is None:
        raise typer.BadParameter("provide PATH or --all / --changed")
    return [path]


@app.callback()
def main_callback() -> None:
    """WorkCopilot Expert Factory."""


@app.command("version")
def version_cmd() -> None:
    console.print(__version__)


@app.command("validate")
def validate_cmd(
    path: Optional[Path] = typer.Argument(None),
    level: str = typer.Option("full", "--level", help="structure|schema|security|full"),
    format: str = typer.Option("text", "--format", help="text|json|both"),
    all_experts: bool = typer.Option(False, "--all", help="all v1 experts under expert-templates"),
    changed: bool = typer.Option(False, "--changed", help="v1 experts changed vs base ref"),
) -> None:
    if level not in {"structure", "schema", "security", "full"}:
        raise typer.BadParameter("invalid level")
    targets = _resolve_targets(path, all_experts, changed)
    failed = False
    for target in targets:
        if not target.is_dir():
            console.print(f"[red]missing[/red] {target}")
            failed = True
            continue
        report = validate_expert(target, level=level)  # type: ignore[arg-type]
        _print_report(report.to_dict(), format)
        if not report.passed:
            failed = True
    if failed:
        raise typer.Exit(code=1)


@app.command("evaluate")
def evaluate_cmd(
    path: Optional[Path] = typer.Argument(None),
    mode: str = typer.Option("full", "--mode", help="static|runtime|full"),
    runtime_profile: Optional[str] = typer.Option(None, "--runtime-profile"),
    timeout: int = typer.Option(180, "--timeout"),
    format: str = typer.Option("both", "--format", help="text|json|both"),
    all_experts: bool = typer.Option(False, "--all"),
    changed: bool = typer.Option(False, "--changed"),
) -> None:
    if mode not in {"static", "runtime", "full"}:
        raise typer.BadParameter("invalid mode")
    from workcopilot_expert_factory.services.evaluate import evaluate_expert

    targets = _resolve_targets(path, all_experts, changed)
    failed = False
    for target in targets:
        try:
            result = evaluate_expert(
                target,
                mode=mode,  # type: ignore[arg-type]
                runtime_profile=runtime_profile,
                timeout=timeout,
            )
        except ExpertFactoryError as exc:
            payload = getattr(exc, "payload", None)
            if payload and format in {"json", "both"}:
                console.print_json(data=payload)
            console.print(f"[red]{exc.code}[/red]: {exc} ({target})")
            failed = True
            if getattr(exc, "exit_code", 1) == 4:
                raise typer.Exit(code=4) from exc
            continue
        if format in {"json", "both"}:
            console.print_json(data=result)
        if format in {"text", "both"}:
            console.print(
                f"[bold green]PASSED[/bold green] {target.name} score={result['score']} "
                f"→ {result.get('report_md')}"
            )
    if failed:
        raise typer.Exit(code=1)


@app.command("build")
def build_cmd(
    path: Optional[Path] = typer.Argument(None),
    output: Path = typer.Option(Path("dist/experts"), "--output", "-o"),
    dev: bool = typer.Option(True, "--dev/--release", help="dev mode may skip evaluation gate"),
    skip_runtime_evaluation: bool = typer.Option(
        True, "--skip-runtime-evaluation/--require-evaluation"
    ),
    all_experts: bool = typer.Option(False, "--all"),
    changed: bool = typer.Option(False, "--changed"),
) -> None:
    targets = _resolve_targets(path, all_experts, changed)
    results = []
    for target in targets:
        try:
            result = build_expert_bundle(
                target,
                output,
                dev=dev,
                skip_runtime_evaluation=skip_runtime_evaluation if dev else False,
            )
            results.append(result)
            console.print_json(data=result)
        except ExpertFactoryError as exc:
            console.print(f"[red]{exc.code}[/red]: {exc} ({target})")
            raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    if len(results) > 1:
        console.print(f"[green]built {len(results)} bundles → {output}[/green]")


@app.command("bind-check")
def bind_check_cmd(
    path: Path = typer.Argument(..., exists=True, file_okay=False),
    env_file: Optional[Path] = typer.Option(None, "--env-file"),
    format: str = typer.Option("text", "--format", help="text|json|both"),
) -> None:
    try:
        result = bind_check(path, env_file)
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    if format in {"json", "both"}:
        console.print_json(data=result)
    if format in {"text", "both"}:
        console.print(f"expert={result.get('expert_id')} slots={len(result.get('slots') or [])}")
        for slot in result.get("slots") or []:
            status = slot.get("status")
            console.print(
                f"  [{status}] {slot.get('slot_id')} missing={slot.get('missing_env') or []}"
            )
        if env_file and not result.get("passed"):
            console.print(f"[yellow]missing env keys:[/yellow] {result.get('missing_env')}")
            raise typer.Exit(code=1)


@app.command("create")
def create_cmd(
    brief: Path = typer.Option(..., "--brief", exists=True, dir_okay=False),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    plan_only: bool = typer.Option(False, "--plan-only"),
    mode: str = typer.Option("single", "--mode", help="single|team"),
) -> None:
    try:
        result = create_expert(brief, output, plan_only=plan_only, mode=mode)
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    console.print_json(data=result)


@app.command("customize")
def customize_cmd(
    source: Path = typer.Argument(..., exists=True, file_okay=False),
    output: Path = typer.Option(..., "--output", "-o"),
    new_id: Optional[str] = typer.Option(None, "--id"),
    notes: Optional[str] = typer.Option(None, "--notes"),
) -> None:
    try:
        result = customize_expert(source, output, new_id=new_id, notes=notes)
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    console.print_json(data=result)


@app.command("inspect")
def inspect_cmd(path: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    expert_yaml = path / "expert.yaml"
    if not expert_yaml.is_file():
        console.print({"legacy": True, "path": str(path), "has_team": (path / "team.yaml").is_file()})
        return
    data = yaml.safe_load(expert_yaml.read_text(encoding="utf-8")) or {}
    meta = data.get("metadata") or {}
    components = data.get("components") or {}
    console.print_json(
        data={
            "expert_id": meta.get("id"),
            "version": meta.get("version"),
            "schema_version": data.get("schema_version"),
            "runtime": data.get("runtime"),
            "skills": [s.get("id") for s in components.get("skills") or []],
            "plugins": [p.get("id") for p in components.get("plugins") or []],
            "connector_slots": [s.get("id") for s in data.get("connector_slots") or []],
            "permissions": data.get("permissions"),
        }
    )


def run() -> None:
    app()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    app()
