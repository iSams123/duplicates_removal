#!/usr/bin/env python3
import os
import re
import sys
import argparse
from pathlib import Path
import time # Import time for stat call

def format_size(size_bytes):
    """Format file size in a human-readable format."""
    if size_bytes is None:
        return "N/A"
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def clean_filename(filename, pattern_compiled, detect_copy):
    """
    Iteratively removes duplicate patterns ((N), .copy, - copy) from a filename's stem.
    Returns the cleaned stem + original suffix.
    """
    path_obj = Path(filename)
    stem = path_obj.stem
    suffix = path_obj.suffix
    
    cleaned_stem = stem
    
    # Keep trying to remove patterns until no more changes are made
    while True:
        original_cleaned_stem = cleaned_stem
        
        # 1. Attempt to remove regex pattern
        # Use search and sub to find/remove pattern anywhere in the stem
        match = pattern_compiled.search(cleaned_stem)
        if match:
            # Replace the matched pattern with an empty string
            # Use span() to get the start and end indices of the match
            start, end = match.span()
            cleaned_stem = cleaned_stem[:start] + cleaned_stem[end:]
            cleaned_stem = cleaned_stem.strip() # Strip potential leading/trailing spaces after removal
            
        # 2. Attempt to remove specific string copy patterns (.copy, - copy) if enabled
        if detect_copy:
            lower_stem = cleaned_stem.lower()
            
            # Find the last occurrence of ".copy" and " - copy" (case-insensitive)
            dot_copy_index = lower_stem.rfind(".copy")
            space_copy_index = lower_stem.rfind(" - copy") # Note: searching for " - copy"

            # Determine which pattern appears last (highest index) in the string
            if space_copy_index > dot_copy_index:
                 # " - copy" is the last pattern found
                 cleaned_stem = cleaned_stem[:space_copy_index].strip()
            elif dot_copy_index != -1: # ".copy" was found, and was not preceded by " - copy" immediately before it
                 # ".copy" is the last pattern found (or the only one)
                 cleaned_stem = cleaned_stem[:dot_copy_index].strip()


        # If no patterns were removed in this pass of checks, we're done
        if cleaned_stem == original_cleaned_stem:
            break

    # Reconstruct filename
    cleaned_filename = cleaned_stem + suffix
    
    # Add a basic safety check - if cleaned_stem is empty after removal but original wasn't
    # This might happen with patterns that consume the whole name e.g. pattern='.*'
    if not cleaned_stem and stem:
         # This warning is more informative if cleaning results in an empty name
         print(f"Warning: Cleaning stem '{stem}' resulted in an empty string.")
         # Decide how to handle this. For grouping, an empty stem might be okay,
         # but it's unusual. Let's proceed but warn.

    return cleaned_filename

def find_and_remove_duplicates(directory_path_str, dry_run=False, pattern=r'\s*\(\d+\)', auto_confirm=False, detect_copy=False, recursive=False):
    """
    Find and remove files with duplicate markers like "(1)", ".copy", or " - copy"
    in the filename. Groups files based on their name after removing patterns and
    keeps the oldest file in each group based on creation time.
    
    Args:
        directory_path_str (str): Directory to scan
        dry_run (bool): If True, only report files that would be deleted without deleting
        pattern (str): Regular expression pattern to match numerical duplicate indicators (e.g., '(1)')
        auto_confirm (bool): If True, skip confirmation prompt
        detect_copy (bool): If True, also detect files ending with ".copy" or " - copy"
        recursive (bool): If True, scan subdirectories recursively
    """
    directory = Path(directory_path_str).expanduser().resolve()
    
    # --- Validate Directory ---
    if not directory.exists():
        print(f"Error: Directory not found at '{directory}'")
        return
    if not directory.is_dir():
        print(f"Error: Path '{directory}' is not a directory.")
        return
    
    print(f"\nScanning directory: '{directory}' for potential duplicates...")
    scan_method = "Recursively" if recursive else "Non-recursively"
    pattern_info = f"using pattern: '{pattern}'" + (f" and detecting '.copy' / ' - copy' patterns" if detect_copy else "")
    print(f"{scan_method} scanning {pattern_info}\n")
    
    # Group files by their "base" name (what they would be after cleaning duplicate markers)
    file_groups = {}
    
    # Compile the regex pattern once
    try:
        pattern_compiled = re.compile(pattern)
    except re.error as e:
        print(f"Error: Invalid regular expression pattern '{pattern}': {e}")
        return

    # Get all files, recursively if specified
    all_files = []
    
    if recursive:
        print("Gathering files recursively...")
        try:
            # We only need files, not dirs or symlinks that aren't files
            all_files = [entry for entry in directory.rglob('*') if entry.is_file()]
        except PermissionError as e:
             print(f"Error accessing directory during recursive scan: {e}")
             print("Scanning may be incomplete due to permissions.")
             # Partial scan - keep files found so far (rglob is a generator)
        except Exception as e:
            print(f"An unexpected error occurred during recursive file gathering: {e}")
            # Decide if you want to halt or continue gathering from other roots
            # For now, continue with files gathered so far
            pass # all_files might be partially populated or empty

        print(f"Found {len(all_files)} files.")
    else:
        try:
            # We only need files, not dirs or symlinks that aren't files
            all_files = [entry for entry in directory.iterdir() if entry.is_file()]
        except PermissionError as e:
            print(f"Error accessing directory {directory}: {e}")
            return # Cannot proceed without listing files
        except Exception as e:
             print(f"An unexpected error occurred during file gathering in {directory}: {e}")
             return

    print("Grouping files...")
    # Group files based on their cleaned name (case-insensitive grouping key)
    for file_path in all_files:
        try:
            # Check if we have permission to read basic file info (like name)
            # and if the file hasn't disappeared.
            # is_file() and stat() checks later will help, but this is a good spot for name cleaning.
            
            # Use the full file path's name for cleaning
            cleaned_name = clean_filename(file_path.name, pattern_compiled, detect_copy)
            
            # The group key should uniquely identify the *set* of duplicates.
            # Combining the parent directory path with the cleaned name makes the key unique per directory.
            # Use lower() for case-insensitive grouping key comparison.
            group_key = str(file_path.parent / cleaned_name).lower()
            
            if group_key not in file_groups:
                file_groups[group_key] = []
            
            file_groups[group_key].append(file_path)
            
        except Exception as e:
            print(f"Error processing file '{file_path.name}' at '{file_path}': {e}")
            # Skip this file if processing fails

    # Filter out groups with only one file (these have no duplicates)
    # Also sort the files within each group by creation time
    groups_with_duplicates = {}
    for group_key, files in file_groups.items():
        if len(files) > 1:
            try:
                # Attempt to get stat for all files in the group before sorting
                # This preemptively catches permission/existence errors for stat()
                files_with_stat = []
                for f in files:
                    try:
                        files_with_stat.append((f, f.stat()))
                    except FileNotFoundError:
                         print(f"Warning: File '{f.name}' not found in group '{Path(group_key).name}'. Skipping.")
                         # Don't add to files_with_stat if not found
                    except PermissionError:
                         print(f"Warning: Permission denied for '{f.name}' in group '{Path(group_key).name}'. Skipping.")
                         # Don't add to files_with_stat if permission denied
                    except Exception as e:
                         print(f"Warning: Could not stat file '{f.name}' in group '{Path(group_key).name}': {e}. Skipping.")
                         # Don't add to files_with_stat if other stat error

                if len(files_with_stat) > 1: # Ensure we still have more than one file after stat filtering
                     # Sort files (Path object) based on the creation time from the stat object
                     files_with_stat.sort(key=lambda item: item[1].st_ctime)
                     # Store just the Path objects back in the group
                     groups_with_duplicates[group_key] = [item[0] for item in files_with_stat]
                else:
                     # If filtering leaves 0 or 1 file, it's no longer a duplicate group
                     # print(f"Info: Group '{Path(group_key).name}' reduced to {len(files_with_stat)} file(s) after stat checks. Skipping.")
                     pass # Skip groups that no longer have duplicates after stat check

            except Exception as e:
                 # Catch any unexpected error during group processing/sorting
                 print(f"Warning: An unexpected error occurred while processing group '{Path(group_key).name}': {e}. Skipping group.")


    file_groups = groups_with_duplicates # Use the filtered and sorted groups

    # Prepare files to delete
    files_to_remove = []
    total_size_to_delete = 0
    
    if not file_groups:
        print("No groups with duplicate files found matching the criteria.")
        if dry_run:
            print("\nThis was a dry run. No files would have been deleted.")
        return

    print("\n--- Duplicate Groups Found ---")
    for group_key, files in file_groups.items():
        if not files: continue # Should not happen with the filtering above, but safeguard

        # The oldest file in the sorted list is the one to keep
        keep_file = files[0]
        
        print(f"Group (from cleaned name: '{Path(group_key).name}')")
        
        try:
            keep_stat = keep_file.stat()
            print(f"  Keeping: '{keep_file.name}' (Oldest, created {time.ctime(keep_stat.st_ctime)})")
            # Show relative path if recursive, or just directory name if not
            display_path = keep_file.parent if recursive else keep_file.parent.name
            if display_path == Path("."): display_path = "Current directory" # Nicer output for '.'
            try:
                 print(f"    Location:                {display_path}")
            except ValueError: # Should not happen for parent, but relative_to might if directory was symlink etc.
                 print(f"    Absolute Path:           {keep_file.parent}")
        except Exception as e:
             print(f"  Keeping: '{keep_file.name}' (Info unavailable: {e})")
             display_path = keep_file.parent if recursive else keep_file.parent.name
             if display_path == Path("."): display_path = "Current directory"
             try:
                  print(f"    Location:                {display_path}")
             except ValueError:
                  print(f"    Absolute Path:           {keep_file.parent}")


        # All other files in the group are duplicates to be removed
        duplicates_in_group = files[1:]
        # No need to check if duplicates_in_group is empty, files[1:] handles it

        for file_to_delete in duplicates_in_group:
            try:
                file_size = file_to_delete.stat().st_size
                total_size_to_delete += file_size
                files_to_remove.append((file_to_delete, file_size))
                print(f"  Deleting: '{file_to_delete.name}' ({format_size(file_size)}) (created {time.ctime(file_to_delete.stat().st_ctime)})")
                display_path = file_to_delete.parent if recursive else file_to_delete.parent.name
                if display_path == Path("."): display_path = "Current directory"
                try:
                    print(f"    Location:                {display_path}")
                except ValueError:
                     print(f"    Absolute Path:           {file_to_delete.parent}")

            except FileNotFoundError:
                 print(f"  Skipping deletion: '{file_to_delete.name}' - File not found.")
            except Exception as e:
                 print(f"  Could not get info for file '{file_to_delete.name}': {e}. Skipping for deletion.")

        print("-" * 20) # Separator between groups
    
    # Re-calculate total size based only on files successfully added to files_to_remove
    total_size_to_delete = sum(size for _, size in files_to_remove)


    # --- Files to be Removed (Preview) ---
    if not files_to_remove:
        print("\nNo files were marked for deletion after processing groups.")
        if dry_run:
            print("This was a dry run. No files would have been deleted.")
        return

    print("\n--- Summary of Files to be Removed ---")
    # Sort files to remove by path for consistent output
    files_to_remove.sort(key=lambda item: str(item[0]).lower())
    
    for file_path, size in files_to_remove:
        print(f"- '{file_path.name}' ({format_size(size)})")
        # Show relative path if recursive, or just directory name if not
        display_path = file_path.parent if recursive else file_path.parent.name
        if display_path == Path("."): display_path = "Current directory"
        try:
            print(f"  Location: {display_path}")
        except ValueError:
             print(f"  Absolute Path: {file_path.parent}")

    print(f"--------------------------------------")
    print(f"Found {len(files_to_remove)} duplicate file(s) to delete (total size: {format_size(total_size_to_delete)}).")
    
    # In dry-run mode, exit here
    if dry_run:
        print("\nThis was a dry run. No files were deleted.")
        return
    
    # Ask for confirmation unless auto-confirm is set
    if not auto_confirm:
        try:
            confirmation = input("Do you want to permanently delete these files? Type 'yes' to confirm: ").strip().lower()
        except EOFError: # Handle input redirection
            print("\nReceived EOF. No confirmation provided. Aborting.")
            return
            
        if confirmation != 'yes':
            print("\nDeletion cancelled by user.")
            return
    
    # Delete the files
    print("\nDeleting files...")
    deleted_count = 0
    deleted_size = 0
    
    # Sort again just before deleting, in case something changed, or just keep alphabetical preview sort
    # Keeping alphabetical preview sort for user feedback consistency.

    for file_path, size in files_to_remove: # Use size from the list, as stat() might fail during deletion
        try:
            # Double check the file still exists before attempting to delete
            if file_path.exists():
                # Get size again just before deleting for accuracy, although we have it from preview list
                # size_before_delete = file_path.stat().st_size
                print(f"Deleting: '{file_path.name}'...", end='')
                display_path = file_path.parent if recursive else file_path.parent.name
                if display_path == Path("."): display_path = "Current directory"
                try:
                    print(f" Location: {display_path}...", end='')
                except ValueError:
                    print(f" Path: {file_path.parent}...", end='')


                file_path.unlink()  # Delete the file
                print(" Success.")
                deleted_count += 1
                deleted_size += size # Use size from list collected earlier
            else:
                 print(f"Skipping: '{file_path.name}' - File no longer exists.")
                 display_path = file_path.parent if recursive else file_path.parent.name
                 if display_path == Path("."): display_path = "Current directory"
                 try:
                     print(f" Location: {display_path}")
                 except ValueError:
                     print(f" Path: {file_path.parent}")


        except PermissionError:
            print(f" Error: Permission denied.")
        except FileNotFoundError:
             # This case should be caught by .exists() check, but as a safeguard
             print(f" Error: File not found.")
        except OSError as e:
            print(f" Error: OS error: {e}")
        except Exception as e:
            print(f" Error: An unexpected error occurred: {e}")
    
    print(f"\nFinished. {deleted_count} file(s) deleted ({format_size(deleted_size)} freed).")


def main():
    parser = argparse.ArgumentParser(
        description="Find and remove duplicate files with markers like '(1)', '.copy', or ' - copy' in the filename.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script identifies potential duplicate files based on patterns in their names
(like '(1)', '(2)', '.copy', ' - copy', etc.). It groups files that reduce
to the same base name after pattern removal and keeps the oldest version of
each file group based on creation time, marking the others for deletion.

Run without arguments for interactive mode. Use arguments for direct execution.

Examples (Command-line):
  # Scan current directory for (N) duplicates
  python duplicate_remover.py .
  
  # Scan Downloads folder recursively for (N) duplicates
  python duplicate_remover.py ~/Downloads --recursive
  
  # Dry run to see what would be deleted in current directory (checking for (N) and .copy/.copy)
  python duplicate_remover.py . --copy --dry-run
  
  # Scan Pictures folder recursively, detect .copy/.copy duplicates, skip confirmation
  python duplicate_remover.py ~/Pictures --recursive --copy --yes
  
  # Use a custom pattern for files with " - Copy" in the name (overrides default pattern)
  python duplicate_remover.py . --pattern " - Copy"
  
  # Use a custom pattern for files with " Copy" (space then Copy) and also detect .copy/.copy
  # This combines regex and the specific string checks.
  # The regex pattern will be checked first in the cleaning process.
  python duplicate_remover.py . --pattern " Copy" --copy

Examples (Interactive mode - run without any arguments):
  python duplicate_remover.py
"""
    )
    parser.add_argument(
        "directory", 
        nargs="?", # Make directory argument optional
        default=".",
        help="Directory to scan (default: current directory)"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Only report files that would be deleted without actually deleting"
    )
    parser.add_argument(
        "--pattern", "-p",
        default=r'\s*\(\d+\)', # Added \s* to handle space before (1)
        help="Regular expression pattern to match numerical duplicate indicators (default: '\\s*\\(\\d+\\)')"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt (use with extreme caution)"
    )
    parser.add_argument(
        "--copy", "-c",
        action="store_true",
        help="Also detect files ending with '.copy' or ' - copy' (case-insensitive)"
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Recursively scan subdirectories."
    )
    
    # --- Handle Interactive Mode if no arguments are provided ---
    # Check if only the script name is in sys.argv
    if len(sys.argv) == 1:
        print("Running in interactive mode.")
        print("-" * 20)
        
        # 1. Prompt for Directory
        target_directory = input("Enter the path to the directory to scan (or press Enter for current directory): ").strip()
        if not target_directory:
            target_directory = "."
            print(f"Using current directory: {Path('.').resolve()}") # Show resolved path

        # 2. Prompt for .copy / - copy Detection
        while True:
            detect_copy_input = input("Also detect files ending with '.copy' or ' - copy'? (y/n, default n): ").strip().lower()
            if detect_copy_input in ('y', 'yes'):
                interactive_detect_copy = True
                break
            elif detect_copy_input in ('n', 'no', ''): # Default is no
                interactive_detect_copy = False
                break
            else:
                print("Invalid input. Please enter 'y' or 'n'.")

        # 3. Prompt for Recursive Scan
        while True:
            recursive_input = input("Scan subdirectories recursively? (y/n, default n): ").strip().lower()
            if recursive_input in ('y', 'yes'):
                interactive_recursive = True
                break
            elif recursive_input in ('n', 'no', ''): # Default is no
                interactive_recursive = False
                break
            else:
                print("Invalid input. Please enter 'y' or 'n'.")

        # Call the main logic function with interactive inputs and default settings for others
        find_and_remove_duplicates(
            target_directory,
            dry_run=False, # Interactive mode doesn't have a dry-run prompt by default
            pattern=r'\s*\(\d+\)', # Use default pattern in interactive mode
            auto_confirm=False, # Interactive mode always asks for confirmation unless -y is passed (which isn't prompted here)
            detect_copy=interactive_detect_copy,
            recursive=interactive_recursive
        )
        
        sys.exit(0) # Exit after interactive mode finishes

    # --- Handle Command-line Mode if arguments ARE provided ---
    args = parser.parse_args()
    
    # Call the main logic function with parsed arguments
    find_and_remove_duplicates(
        args.directory,
        args.dry_run,
        args.pattern,
        args.yes,
        args.copy,
        args.recursive
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user (Ctrl+C).")
        sys.exit(1)
    except Exception as e:
        # Print traceback for unhandled exceptions in command-line mode
        if len(sys.argv) > 1:
             import traceback
             traceback.print_exc(file=sys.stderr)
        print(f"\nAn unhandled error occurred: {e}", file=sys.stderr)
        sys.exit(1)