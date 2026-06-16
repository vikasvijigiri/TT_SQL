package handlers

import (
	"bufio"
	"encoding/json"
	"os"
	"sync"
)

var (
	examplesOnce  sync.Once
	examplesCache map[string]map[string]any
)

// getAllExamples loads and caches the spider2-lite-snowflake.jsonl data.
// Returns a map: instance_id â†’ full record.
func getAllExamples(inputDir string) map[string]map[string]any {
	// We can't use sync.Once here because inputDir varies; but in practice it's always
	// the same value, so we initialise once and cache.
	examplesOnce.Do(func() {
		examplesCache = loadExamples(inputDir)
	})
	return examplesCache
}

func loadExamples(inputDir string) map[string]map[string]any {
	path := inputDir + "/spider2-lite-snowflake.jsonl"
	examples := map[string]map[string]any{}
	f, err := os.Open(path)
	if err != nil {
		return examples
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 4*1024*1024), 4*1024*1024) // 4 MB per line
	for sc.Scan() {
		line := sc.Text()
		if line == "" {
			continue
		}
		var rec map[string]any
		if err := json.Unmarshal([]byte(line), &rec); err != nil {
			continue
		}
		if id, ok := rec["instance_id"].(string); ok {
			examples[id] = rec
		}
	}
	return examples
}

// readJSONL reads a JSONL file and returns all records as []map[string]any.
func readJSONL(path string) []map[string]any {
	f, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer f.Close()
	var records []map[string]any
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 4*1024*1024), 4*1024*1024)
	for sc.Scan() {
		line := sc.Text()
		if line == "" {
			continue
		}
		var rec map[string]any
		if err := json.Unmarshal([]byte(line), &rec); err != nil {
			continue
		}
		records = append(records, rec)
	}
	return records
}
