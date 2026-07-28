from __future__ import annotations

import os
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
from workcopilot_expert_factory.events import emit, new_trace_id
from workcopilot_expert_factory.services.batch import select_experts
from workcopilot_expert_factory.services.bind_check import bind_check
from workcopilot_expert_factory.services.create import create_expert
from workcopilot_expert_factory.services.customize import customize_expert
from workcopilot_expert_factory.validators.expert import validate_expert

app = typer.Typer(
    name="expert",
    help="WorkCopilot Expert Factory CLI v2.1",
    no_args_is_help=True,
    add_completion=False,
)
branch_app = typer.Typer(help="Expert asset branch (copy-on-write)", no_args_is_help=True)
publish_app = typer.Typer(help="Publish Expert Bundle to Nacos", no_args_is_help=True)
app.add_typer(branch_app, name="branch")
app.add_typer(publish_app, name="publish")

console = Console()

VALIDATE_LEVELS = {"structure", "schema", "security", "dependencies", "runtime", "release", "full"}


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
def main_callback(
    trace_id: Optional[str] = typer.Option(None, "--trace-id", help="observability trace id"),
    quiet: bool = typer.Option(False, "--quiet", help="suppress event logs"),
    verbose: bool = typer.Option(False, "--verbose", help="verbose mode"),
) -> None:
    new_trace_id(trace_id)
    if quiet:
        os.environ["WORKCOPILOT_QUIET"] = "1"
    if verbose:
        os.environ["WORKCOPILOT_VERBOSE"] = "1"


@app.command("version")
def version_cmd() -> None:
    console.print(__version__)


@app.command("validate")
def validate_cmd(
    path: Optional[Path] = typer.Argument(None),
    level: str = typer.Option("full", "--level", help="structure|schema|security|dependencies|runtime|release|full"),
    format: str = typer.Option("text", "--format", help="text|json|both"),
    all_experts: bool = typer.Option(False, "--all", help="all v1 experts under expert-templates"),
    changed: bool = typer.Option(False, "--changed", help="v1 experts changed vs base ref"),
) -> None:
    if level not in VALIDATE_LEVELS:
        raise typer.BadParameter(f"invalid level; choose from {sorted(VALIDATE_LEVELS)}")
    targets = _resolve_targets(path, all_experts, changed)
    failed = False
    for target in targets:
        emit("expert.validate.started", expert_path=str(target), level=level)
        if not target.exists():
            console.print(f"[red]missing[/red] {target}")
            failed = True
            continue
        report = validate_expert(target, level=level)  # type: ignore[arg-type]
        _print_report(report.to_dict(), format)
        emit(
            "expert.validate.completed" if report.passed else "expert.validate.failed",
            status="success" if report.passed else "failed",
            expert_path=str(target),
        )
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
        emit("expert.evaluate.started", expert_path=str(target), mode=mode)
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
            emit("expert.evaluate.failed", status="failed", expert_path=str(target), error_code=exc.code)
            failed = True
            if getattr(exc, "exit_code", 1) == 4:
                raise typer.Exit(code=4) from exc
            continue
        if format in {"json", "both"}:
            console.print_json(data=result)
        if format in {"text", "both"}:
            console.print(
                f"[bold green]PASSED[/bold green] {target.name} score={result['score']} "
                f"digest={result.get('source_digest')} → {result.get('report_md')}"
            )
        emit("expert.evaluate.completed", expert_id=result.get("expert_id"), version=result.get("version"))
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
    signature_mode: Optional[str] = typer.Option(None, "--signature-mode", help="none|local-key|cosign|kms"),
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
                signature_mode=signature_mode,
            )
            results.append(result)
            console.print_json(data=result)
            emit("expert.build.completed", expert_id=result.get("expert_id"), version=result.get("version"))
        except ExpertFactoryError as exc:
            console.print(f"[red]{exc.code}[/red]: {exc} ({target})")
            emit("expert.build.failed", status="failed", error_code=exc.code)
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
    brief: Optional[Path] = typer.Option(None, "--brief", exists=True, dir_okay=False),
    requirements: Optional[Path] = typer.Option(None, "--requirements", exists=True, dir_okay=False),
    plan: Optional[Path] = typer.Option(None, "--plan", exists=True, dir_okay=False, help="existing Expert Plan YAML"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    plan_only: bool = typer.Option(False, "--plan-only"),
    mode: str = typer.Option("single", "--mode", help="single|team"),
) -> None:
    try:
        result = create_expert(
            brief,
            output,
            requirements=requirements,
            plan_path=plan,
            plan_only=plan_only,
            mode=mode,
        )
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    emit("expert.create.completed", expert_id=result.get("expert_id"))
    console.print_json(data=result)


@app.command("customize")
def customize_cmd(
    source: Path = typer.Argument(..., exists=True, file_okay=False),
    output: Path = typer.Option(..., "--output", "-o"),
    new_id: Optional[str] = typer.Option(None, "--id"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    spec: Optional[Path] = typer.Option(None, "--spec", exists=True, dir_okay=False),
    allow_permission_expansion: bool = typer.Option(False, "--allow-permission-expansion"),
) -> None:
    try:
        result = customize_expert(
            source,
            output,
            new_id=new_id,
            notes=notes,
            spec_path=spec,
            allow_permission_expansion=allow_permission_expansion,
        )
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    emit("expert.customize.completed", expert_path=str(output))
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
            "release": data.get("release"),
        }
    )


@branch_app.command("create")
def branch_create_cmd(
    source: Path = typer.Argument(..., exists=True, file_okay=False),
    name: str = typer.Option(..., "--name"),
    target_id: Optional[str] = typer.Option(None, "--target-id"),
) -> None:
    from workcopilot_expert_factory.services.branch import create_branch

    try:
        result = create_branch(source, name=name, target_id=target_id)
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    emit("expert.branch.created", branch_path=result.get("branch_path"))
    console.print_json(data=result)


@branch_app.command("status")
def branch_status_cmd(path: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    from workcopilot_expert_factory.services.branch import branch_status

    try:
        result = branch_status(path)
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    console.print_json(data=result)


@branch_app.command("diff")
def branch_diff_cmd(path: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    from workcopilot_expert_factory.services.branch import branch_diff

    try:
        result = branch_diff(path)
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    console.print_json(data=result)


@branch_app.command("rebase")
def branch_rebase_cmd(
    path: Path = typer.Argument(..., exists=True, file_okay=False),
    onto: Optional[Path] = typer.Option(None, "--onto", exists=True, file_okay=False),
) -> None:
    from workcopilot_expert_factory.services.branch import branch_rebase

    try:
        result = branch_rebase(path, onto=onto)
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        if getattr(exc, "payload", None):
            console.print_json(data=exc.payload)
        emit("expert.branch.conflicted", status="failed", error_code=exc.code)
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    emit("expert.branch.rebased", branch_path=str(path))
    console.print_json(data=result)


@branch_app.command("materialize")
def branch_materialize_cmd(
    path: Path = typer.Argument(..., exists=True, file_okay=False),
    output: Path = typer.Option(..., "--output", "-o"),
) -> None:
    from workcopilot_expert_factory.services.branch import materialize_branch

    try:
        result = materialize_branch(path, output)
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    console.print_json(data=result)


@publish_app.callback(invoke_without_command=True)
def publish_main(
    ctx: typer.Context,
    bundle: Optional[Path] = typer.Argument(None),
    target: str = typer.Option("nacos-dev", "--target"),
    stage: str = typer.Option("draft", "--stage", help="draft|review|online"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    wait: bool = typer.Option(False, "--wait"),
    overwrite_draft: bool = typer.Option(False, "--overwrite-draft"),
    update_latest: bool = typer.Option(False, "--update-latest"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if bundle is None:
        raise typer.BadParameter("BUNDLE path required")
    if stage not in {"draft", "review", "online"}:
        raise typer.BadParameter("invalid stage")
    from workcopilot_expert_factory.services.publish import publish_expert

    try:
        result = publish_expert(
            bundle,
            target=target,
            stage=stage,  # type: ignore[arg-type]
            dry_run=dry_run,
            wait=wait,
            overwrite_draft=overwrite_draft,
            update_latest=update_latest,
        )
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    console.print_json(data=result)


@publish_app.command("resume")
def publish_resume_cmd(record: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    from workcopilot_expert_factory.services.publish import resume_publish

    try:
        result = resume_publish(record)
    except ExpertFactoryError as exc:
        console.print(f"[red]{exc.code}[/red]: {exc}")
        raise typer.Exit(code=getattr(exc, "exit_code", 1)) from exc
    console.print_json(data=result)


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
