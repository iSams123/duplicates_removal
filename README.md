# Duplicate File Remover

This Python script helps you find and remove duplicate files in a directory. It identifies potential duplicate files based on patterns in their names (like '(1)', '(2)', '.copy', ' - copy', etc.). It groups files that reduce to the same base name after pattern removal and keeps the oldest version of each file group based on creation time, marking the others for deletion.

## Features

*   Finds duplicate files based on name patterns.
*   Supports custom regular expression patterns for identifying duplicates.
*   Detects and handles ".copy" and " - copy" patterns.
*   Recursive directory scanning.
*   Dry-run mode to preview changes before deleting files.
*   Interactive mode for easy configuration.

## Usage

The script can be run from the command line or in interactive mode.

### Command-line Mode

```bash
python duplicates_remove_v6.py <directory> [options]
```

*   `<directory>`: The directory to scan (default: current directory).
*   `--dry-run` or `-d`: Only report files that would be deleted without actually deleting.
*   `--pattern` or `-p`: Regular expression pattern to match numerical duplicate indicators (default: '\s*\(\d+\)').
*   `--yes` or `-y`: Skip confirmation prompt (use with extreme caution).
*   `--copy` or `-c`: Also detect files ending with '.copy' or ' - copy' (case-insensitive).
*   `--recursive` or `-r`: Recursively scan subdirectories.

Example:

```bash
python duplicates_remove_v6.py ~/Downloads --recursive --copy --yes
```

### Interactive Mode

Run the script without any arguments to start interactive mode. The script will prompt you for the directory to scan, whether to detect ".copy" and " - copy" patterns, and whether to scan subdirectories recursively.

```bash
python duplicates_remove_v6.py
```

## Dependencies

*   Python 3.6 or higher
*   No external libraries are required.

## Author

iSams123

## License

This project is licensed under the MIT License.