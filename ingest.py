#!/usr/bin/env python3
"""
CLI ingestion script.

Drop any .pdf, .txt, or .md files into the data/ folder, then run:

    python ingest.py

The script scans data/ recursively, ingests new/changed files, and skips
files that are already up-to-date in the vector store.

Options:
    --clear     Wipe the entire knowledge base before ingesting
    --data-dir  Path to the folder to scan (default: ./data)
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent))

from rag.ingestion import clear_collection, ingest_file, list_ingested_files

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}
console = Console()


def scan_data_folder(data_dir: Path) -> list[Path]:
    """Recursively find all supported files in data_dir."""
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(data_dir.rglob(f"*{ext}"))
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description="Ingest documents from the data/ folder into ChromaDB.")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the entire knowledge base before ingesting.",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(Path(__file__).parent / "data"),
        help="Path to the folder containing documents (default: ./data).",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        console.print(f"[red]Error:[/red] data directory not found: {data_dir}")
        sys.exit(1)

    console.print(Panel.fit("[bold cyan]RAG Document Ingestion[/bold cyan]", border_style="cyan"))

    if args.clear:
        console.print("[yellow]Clearing existing knowledge base...[/yellow]")
        clear_collection()
        console.print("[green]Knowledge base cleared.[/green]\n")

    files = scan_data_folder(data_dir)

    if not files:
        console.print(
            f"[yellow]No supported files found in {data_dir}[/yellow]\n"
            f"Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
        sys.exit(0)

    console.print(f"Found [bold]{len(files)}[/bold] file(s) in [cyan]{data_dir}[/cyan]\n")

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Ingesting...", total=len(files))

        for file_path in files:
            progress.update(task, description=f"[cyan]{file_path.name}[/cyan]")
            try:
                result = ingest_file(str(file_path))
                results.append(result)
            except Exception as e:
                results.append({"status": "error", "file": file_path.name, "chunks": 0, "error": str(e)})
            progress.advance(task)

    # Summary table
    table = Table(title="\nIngestion Summary", show_lines=True)
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Chunks", justify="right")

    status_colors = {"added": "green", "updated": "yellow", "skipped": "dim", "error": "red"}
    status_icons = {"added": "✓ added", "updated": "↺ updated", "skipped": "– skipped", "error": "✗ error"}

    for r in results:
        color = status_colors.get(r["status"], "white")
        label = status_icons.get(r["status"], r["status"])
        extra = f"\n[red dim]{r.get('error', '')}[/red dim]" if r["status"] == "error" else ""
        table.add_row(
            r["file"] + extra,
            f"[{color}]{label}[/{color}]",
            str(r["chunks"]) if r["status"] != "error" else "-",
        )

    console.print(table)

    # Totals
    added = sum(1 for r in results if r["status"] == "added")
    updated = sum(1 for r in results if r["status"] == "updated")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    total_chunks = sum(r["chunks"] for r in results if r["status"] != "error")

    console.print(
        f"\n[bold]Done.[/bold] "
        f"[green]{added} added[/green]  "
        f"[yellow]{updated} updated[/yellow]  "
        f"[dim]{skipped} skipped[/dim]  "
        f"[red]{errors} errors[/red]  "
        f"│  [bold cyan]{total_chunks} total chunks[/bold cyan] in knowledge base"
    )

    # Show full KB state
    ingested = list_ingested_files()
    if ingested:
        console.print("\n[bold]Knowledge base now contains:[/bold]")
        for item in ingested:
            console.print(f"  • {item['file']}  ([cyan]{item['chunks']} chunks[/cyan])")


if __name__ == "__main__":
    main()
