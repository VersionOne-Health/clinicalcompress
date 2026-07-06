"""Command-line interface for clinicalcompress.

Copyright 2026 Anurag Chatterjee
Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

from clinicalcompress.api import compress
from clinicalcompress.protect import protect

console = Console()

DISCLAIMER = (
    "clinicalcompress is a text-compression utility, not a medical device. "
    "It is not clinically validated and must not be used as the sole basis "
    "for clinical decisions. Always review compressed output before use."
)

_disclaimer_shown = False


def _show_disclaimer_once() -> None:
    global _disclaimer_shown
    if not _disclaimer_shown:
        console.print(f"[yellow]Notice:[/yellow] {DISCLAIMER}\n")
        _disclaimer_shown = True


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        console.print(f"[red]Error reading '{path}': {exc}[/red]")
        sys.exit(1)


@click.group()
@click.version_option(package_name="clinicalcompress")
def cli() -> None:
    """clinicalcompress: compress clinical text without flipping a negation."""
    _show_disclaimer_once()


@cli.command()
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="Path to a clinical note text file.")
@click.option("--reduction", "target_reduction", default=0.4, type=float, show_default=True, help="Target fractional reduction (0-1).")
@click.option("--use-llm", is_flag=True, default=False, help="Also apply optional LLM compression to unprotected spans (requires ANTHROPIC_API_KEY).")
def run(file_path: str, target_reduction: float, use_llm: bool) -> None:
    """Compress a clinical note and print the result plus a safety report."""
    import os

    text = _read_file(file_path)
    llm_config = {"api_key": os.environ.get("ANTHROPIC_API_KEY")} if use_llm else None
    result = compress(text, target_reduction=target_reduction, use_llm=use_llm, llm_config=llm_config)

    console.rule("[bold]Compressed text[/bold]")
    console.print(result.compressed_text)

    console.rule("[bold]Safety report[/bold]")
    table = Table(show_lines=False)
    table.add_column("Check")
    table.add_column("Category")
    table.add_column("Result")
    table.add_column("Detail")
    for check in result.safety.checks:
        status = "[green]PASS[/green]" if check.passed else "[red]FAIL[/red]"
        category = check.span.category.value if check.span else "-"
        table.add_row(check.name, category, status, check.detail)
    console.print(table)

    if result.safety.reverted_spans:
        console.print("[yellow]Reverted spans:[/yellow]")
        for item in result.safety.reverted_spans:
            console.print(f"  - {item}")

    console.rule("[bold]Tokens[/bold]")
    console.print(
        f"original={result.original_tokens}  compressed={result.compressed_tokens}  "
        f"reduction={result.reduction_pct}%"
    )


@cli.command()
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="Path to a clinical note text file.")
def check(file_path: str) -> None:
    """Show what would be protected in a clinical note, without compressing."""
    text = _read_file(file_path)
    spans = protect(text)

    console.rule("[bold]Protected spans[/bold]")
    table = Table(show_lines=False)
    table.add_column("Category")
    table.add_column("Text")
    table.add_column("Governs")
    table.add_column("Offset")
    for span in spans:
        table.add_row(span.category.value, span.text, span.governs or "-", f"{span.start}-{span.end}")
    console.print(table)
    console.print(f"\n[bold]{len(spans)}[/bold] protected span(s) found.")


if __name__ == "__main__":
    cli()
