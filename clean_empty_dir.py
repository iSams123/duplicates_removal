import os
import sys
from pathlib import Path
import click # External dependency: pip install click

# The core logic function remains largely the same,
# but now it should ideally just take its parameters and return results.
# The CLI interactions (print, confirm) are handled by click.

def delete_empty_dirs_recursive(root_dir_path: Path, dry_run: bool = False):
    """
    Recursively finds and (optionally) deletes empty directories
    starting from root_dir_path.

    Args:
        root_dir_path (pathlib.Path): The path to the directory to start searching from.
        dry_run (bool): If True, only report what would be deleted.

    Returns:
        tuple: (deleted_count, error_count)
    """
    deleted_count = 0
    error_count = 0

    for dirpath_str, dirnames, filenames in os.walk(root_dir_path, topdown=False):
        current_dir = Path(dirpath_str)
        try:
            # Check if the directory is empty
            if not list(current_dir.iterdir()):
                if dry_run:
                    click.echo(f"DRY-RUN: Directory '{current_dir}' is empty. Would delete.")
                    deleted_count += 1
                else:
                    click.echo(f"Directory '{current_dir}' is empty. Deleting...")
                    try:
                        current_dir.rmdir()
                        click.echo(click.style(f"  Deleted: '{current_dir}'", fg="green"))
                        deleted_count += 1
                    except OSError as e:
                        click.echo(click.style(f"  Error deleting '{current_dir}': {e}", fg="red"), err=True)
                        error_count += 1
            # else: # For debugging if needed
            #     if list(current_dir.iterdir()):
            #         click.echo(f"Info: Directory '{current_dir}' contains: {', '.join(p.name for p in current_dir.iterdir())}")
            #     else:
            #         click.echo(f"Info: Directory '{current_dir}' is technically empty but not caught by logic?")


        except OSError as e:
             click.echo(click.style(f"  Error accessing or listing contents of '{current_dir}': {e}", fg="red"), err=True)
             error_count += 1
    return deleted_count, error_count

@click.command()
@click.argument(
    "root_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True, path_type=Path),
    # path_type=Path ensures the argument is converted to a Path object
)
@click.option(
    "--dry-run",
    is_flag=True, # Makes it a boolean flag, e.g., --dry-run
    help="Perform a dry run: show what would be deleted without actually deleting."
)
@click.option(
    "-y", "--yes",
    is_flag=True,
    help="Automatically confirm deletion (use with caution).",
    # This makes click.confirm behave as if 'yes' was pressed if this flag is present
    # We can check this flag before calling click.confirm, or use it to bypass confirmation
)
def cli(root_dir: Path, dry_run: bool, yes: bool):
    """
    Recursively finds and deletes empty directories starting from ROOT_DIR.
    """
    click.echo(f"\nStarting search in: '{root_dir.resolve()}'")

    if dry_run:
        click.echo(click.style("DRY-RUN mode enabled. No directories will be deleted.", fg="yellow"))
    else:
        if not yes: # Only ask for confirmation if --yes is not provided
            if not click.confirm(
                click.style("Warning: This will permanently delete empty directories. Are you sure?", fg="yellow"),
                default=False, # Default to No if user just hits Enter
                abort=True # Abort if user says no
            ):
                # This part is actually unreachable if abort=True and user says no
                # click.confirm with abort=True will exit if confirmation fails.
                # Kept for clarity if abort=False was used.
                # click.echo("Operation cancelled by user.")
                # sys.exit(0)
                pass # If abort=True, script exits before this.
            else:
                click.echo("Proceeding with deletion...")


    deleted_count, error_count = delete_empty_dirs_recursive(root_dir, dry_run)

    click.echo("\n--- Summary ---")
    if dry_run:
        click.echo(f"Would have deleted: {click.style(str(deleted_count), fg='cyan')} directories.")
    else:
        click.echo(f"Successfully deleted: {click.style(str(deleted_count), fg='green')} directories.")

    if error_count > 0:
        click.echo(f"Encountered errors: {click.style(str(error_count), fg='red')} (check messages above).")
    click.echo("-------------")

    if deleted_count == 0 and error_count == 0:
        if dry_run:
            click.echo("No empty directories found that would be deleted.")
        else:
            click.echo("No empty directories found or deleted.")
    click.echo("\nProcess finished.")

if __name__ == "__main__":
    cli()