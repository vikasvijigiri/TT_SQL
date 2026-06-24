// Package archive ports the Python get_target_dirs_for_date logic.
package archive

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// GetTargetDirsForDate returns the list of result directories to scan for a given date string.
// date == "all"  â†’ live dir + all archives
// date == today  â†’ live dir + today's archives
// date == other  â†’ only matching archives
func GetTargetDirsForDate(baseDir, date string) []string {
	var dirs []string
	today := time.Now().Format("2006-01-02")

	if date == "all" {
		dirs = append(dirs, baseDir)
		archiveBase := filepath.Join(baseDir, "_archive")
		if entries, err := os.ReadDir(archiveBase); err == nil {
			for _, e := range entries {
				if e.IsDir() {
					dirs = append(dirs, filepath.Join(archiveBase, e.Name()))
				}
			}
		}
		return dirs
	}

	if date == today {
		dirs = append(dirs, baseDir)
	}

	archiveBase := filepath.Join(baseDir, "_archive")
	if entries, err := os.ReadDir(archiveBase); err == nil {
		for _, e := range entries {
			if !e.IsDir() {
				continue
			}
			parts := strings.SplitN(e.Name(), "_", 2)
			if len(parts) < 2 {
				continue
			}
			ds := parts[1] // YYYYMMDD or YYYYMMDD_HHMMSS
			if len(ds) >= 8 {
				runDate := fmt.Sprintf("%s-%s-%s", ds[:4], ds[4:6], ds[6:8])
				if runDate == date {
					dirs = append(dirs, filepath.Join(archiveBase, e.Name()))
				}
			}
		}
	}
	return dirs
}

// IsDabPath returns true if any path component (case-insensitive) equals "dab".
func IsDabPath(path string) bool {
	for _, part := range strings.Split(filepath.ToSlash(path), "/") {
		if strings.EqualFold(part, "dab") {
			return true
		}
	}
	return false
}

// IsArchivePath returns true if any path component equals "_archive".
func IsArchivePath(path string) bool {
	for _, part := range strings.Split(filepath.ToSlash(path), "/") {
		if part == "_archive" {
			return true
		}
	}
	return false
}

// WalkMDFiles returns all .md files under dir, optionally excluding _archive and dab paths.
func WalkMDFiles(dir string, excludeArchive, excludeDab bool) []string {
	var files []string
	_ = filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		if filepath.Ext(path) != ".md" {
			return nil
		}
		rel, _ := filepath.Rel(dir, path)
		if excludeArchive && IsArchivePath(rel) {
			return nil
		}
		if excludeDab && IsDabPath(rel) {
			return nil
		}
		files = append(files, path)
		return nil
	})
	return files
}
