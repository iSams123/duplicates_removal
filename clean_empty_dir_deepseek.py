import os
import sys
from pathlib import Path
import click
from loguru import logger
from send2trash import send2trash

# Configure loguru for clean output
logger.remove()
# Customize format for verbosity later if needed
logger.add(sys.stderr, format="<level>{level: <8}</level> | <cyan>{message}</cyan>", level="INFO")


def delete_empty_recursive(root_dir_path: Path, force_delete: bool, verbose_level: int):
    """
    Recursively finds and removes empty directories using os.walk for traversal
    and pathlib for operations.

    Args:
        root_dir_path (Path): The path to the directory to start searching from.
        force_delete (bool): If True, permanently delete. Otherwise, send to trash.
        verbose_level (int): Verbosity level for logging.

    Returns:
        tuple: (deleted_count, error_count)
    """
    deleted_count = 0
    error_count = 0

    if verbose_level >= 2: # Extremely verbose
        logger.opt(depth=1).info("Log level set to TRACE")
        logger.remove()
        logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", level="TRACE")
    elif verbose_level == 1: # Debug
        logger.opt(depth=1).info("Log level set to DEBUG")
        logger.remove()
        logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", level="DEBUG")
    # Else, default INFO level remains

    # Walk the directory tree bottom-up
    for dirpath_str, dirnames, filenames in os.walk(root_dir_path, topdown=False):
        current_dir = Path(dirpath_str)
        logger.trace(f"Checking directory: {current_dir}")

        # Don't try to delete the root_dir_path itself within the os.walk loop if it's the starting point
        # It will be handled after the loop if it's empty
        # However, os.walk(topdown=False) processes children first, so this isn't strictly
        # necessary for `current_dir == root_dir_path` unless `root_dir_path` has no subdirs.
        # More importantly, we want to avoid processing non-directories if os.walk somehow yielded one (shouldn't happen for dirpath).

        try:
            # Check if the directory is empty
            # list(current_dir.iterdir()) is fine, or use `any` for slight optimization
            # if not any(current_dir.iterdir()): # More efficient for just checking emptiness
            if not list(current_dir.iterdir()):
                logger.debug(f"Found empty directory: {current_dir}")

                if force_delete:
                    current_dir.rmdir()
                    logger.info(f"Permanently deleted: {current_dir}")
                else:
                    send2trash(str(current_dir)) # send2trash needs a string path
                    logger.info(f"Sent to trash: {current_dir}")
                deleted_count += 1
            else:
                if verbose_level >=2: # TRACE level example
                    contents = [p.name for p in current_dir.iterdir()]
                    logger.trace(f"Directory '{current_dir}' not empty. Contains: {contents[:5]}{'...' if len(contents) > 5 else ''}")


        except FileNotFoundError:
            # This can happen if a parent directory was deleted in a previous iteration
            # and it contained this current_dir.
            logger.trace(f"Directory {current_dir} not found, likely deleted as part of an empty parent.")
            pass # It's already gone or was part of a parent that was deleted.
        except OSError as e:
            # Handles permission errors for listdir or rmdir/send2trash
            error_count += 1
            logger.error(f"Error processing '{current_dir}': {e}")

    # Final check for the root directory itself, in case it became empty
    # This is important because os.walk might not yield the root if it had no subdirs
    # or it's just cleaner to handle it post-loop.
    try:
        if root_dir_path.exists() and not list(root_dir_path.iterdir()):
            logger.debug(f"Root directory '{root_dir_path}' is now empty.")
            if force_delete:
                root_dir_path.rmdir()
                logger.info(f"Permanently deleted root directory: {root_dir_path}")
            else:
                send2trash(str(root_dir_path))
                logger.info(f"Sent root directory to trash: {root_dir_path}")
            deleted_count += 1
    except OSError as e:
        error_count += 1
        logger.error(f"Error processing root directory '{root_dir_path}' after scan: {e}")


    return deleted_count, error_count


@click.command()
@click.argument("root_dir", type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True, path_type=Path))
@click.option("--force", is_flag=True, help="Permanently delete instead of sending to trash.")
@click.option("-v", "--verbose", count=True, help="Increase output verbosity (-v for DEBUG, -vv for TRACE).")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt.")
def cli(root_dir: Path, force: bool, verbose: int, yes: bool):
    """
    Recursively find and remove empty directories.
    By default, sends directories to trash. Use --force for permanent deletion.
    """
    # Adjust logger level based on verbosity (done inside the function now)

    click.echo(f"Scanning: {root_dir.resolve()}")
    if not force:
        click.echo(click.style("Mode: Sending to Trash (use --force to delete permanently)", fg="yellow"))
    else:
        click.echo(click.style("Mode: Permanent Deletion", fg="red", bold=True))

    if not force and not yes:
        if not click.confirm(f"Are you sure you want to process '{root_dir}' and send empty subdirectories to trash?", default=False, abort=True):
            pass # Unreachable if abort=True
    elif force and not yes:
        if not click.confirm(click.style(f"WARNING: You are about to PERMANENTLY DELETE empty subdirectories in '{root_dir}'. This cannot be undone. Proceed?", fg="red"), default=False, abort=True):
            pass

    deleted, errors = delete_empty_recursive(root_dir, force, verbose)

    logger.success(f"Operation complete!") # loguru's success level
    summary_message = f"Directories processed: {deleted + errors}, Successfully removed: {deleted}"
    if errors:
        summary_message += f", Errors encountered: {errors}"
    click.echo(summary_message)
    if errors:
        click.echo(click.style("Please review error messages above.", fg="red"))


if __name__ == "__main__":
    cli()