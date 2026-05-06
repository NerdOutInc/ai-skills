package main

import (
	"encoding/json"
	"io"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"
)

const maxNotes = 200

// Note is a free-form message sent from the web page to the agent.
// OffsetMs is milliseconds since the recording's started_at, or -1 when
// no take was active when the note arrived. ConsumedAt is set when the
// agent acknowledges the note via POST /api/notes/consumed (or the
// CLI's `notes --clear`); the note itself is preserved so the page can
// show that the agent has seen it.
type Note struct {
	ID         int        `json:"id"`
	At         time.Time  `json:"at"`
	OffsetMs   int64      `json:"offset_ms"`
	Text       string     `json:"text"`
	ConsumedAt *time.Time `json:"consumed_at,omitempty"`
}

type noteStore struct {
	mu     sync.RWMutex
	nextID int
	items  []Note
}

func newNoteStore() *noteStore {
	return &noteStore{items: []Note{}}
}

func (ns *noteStore) add(text string, takeStart *time.Time) Note {
	ns.mu.Lock()
	defer ns.mu.Unlock()

	now := time.Now()
	offset := int64(-1)
	if takeStart != nil {
		offset = now.Sub(*takeStart).Milliseconds()
		if offset < 0 {
			offset = 0
		}
	}

	ns.nextID++
	n := Note{
		ID:       ns.nextID,
		At:       now,
		OffsetMs: offset,
		Text:     text,
	}
	ns.items = append(ns.items, n)
	if len(ns.items) > maxNotes {
		ns.items = ns.items[len(ns.items)-maxNotes:]
	}
	return n
}

// list returns notes with id strictly greater than sinceID. When
// includeConsumed is false, only notes without a consumed_at are returned.
func (ns *noteStore) list(sinceID int, includeConsumed bool) []Note {
	ns.mu.RLock()
	defer ns.mu.RUnlock()
	out := make([]Note, 0, len(ns.items))
	for _, n := range ns.items {
		if n.ID <= sinceID {
			continue
		}
		if !includeConsumed && n.ConsumedAt != nil {
			continue
		}
		out = append(out, n)
	}
	return out
}

// markAllConsumed stamps ConsumedAt on every currently-unconsumed note.
// Returns the count of notes that were newly marked.
func (ns *noteStore) markAllConsumed() int {
	ns.mu.Lock()
	defer ns.mu.Unlock()
	now := time.Now()
	count := 0
	for i := range ns.items {
		if ns.items[i].ConsumedAt == nil {
			t := now
			ns.items[i].ConsumedAt = &t
			count++
		}
	}
	return count
}

func (ns *noteStore) clear() {
	ns.mu.Lock()
	defer ns.mu.Unlock()
	ns.items = ns.items[:0]
}

// installNoteRoutes wires the notes endpoints onto mux. The take-start
// lookup is supplied by the status store so notes can be stamped with a
// recording-relative offset.
func installNoteRoutes(mux *http.ServeMux, ns *noteStore, st *store) {
	mux.HandleFunc("/api/note", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", "POST")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 16*1024))
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
			return
		}
		var p struct {
			Text string `json:"text"`
		}
		if len(body) == 0 {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "empty body"})
			return
		}
		if err := json.Unmarshal(body, &p); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json: " + err.Error()})
			return
		}
		text := strings.TrimSpace(p.Text)
		if text == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "text is required"})
			return
		}
		if len([]rune(text)) > 1000 {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "text too long"})
			return
		}

		var takeStart *time.Time
		snap := st.snapshot()
		if snap.StartedAt != nil {
			t := *snap.StartedAt
			takeStart = &t
		}

		writeJSON(w, http.StatusOK, ns.add(text, takeStart))
	})

	mux.HandleFunc("/api/notes", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			sinceID := 0
			if v := r.URL.Query().Get("since_id"); v != "" {
				if n, err := strconv.Atoi(v); err == nil && n >= 0 {
					sinceID = n
				}
			}
			// includeConsumed defaults to true so the page can display
			// "seen by agent" status. The agent's CLI passes ?status=open
			// (or includes it explicitly) to filter to unconsumed only.
			includeConsumed := true
			switch strings.ToLower(r.URL.Query().Get("status")) {
			case "open", "unconsumed", "queued":
				includeConsumed = false
			}
			items := ns.list(sinceID, includeConsumed)
			writeJSON(w, http.StatusOK, map[string]any{
				"notes": items,
				"count": len(items),
			})
		case http.MethodDelete:
			ns.clear()
			writeJSON(w, http.StatusOK, map[string]any{"cleared": true})
		default:
			w.Header().Set("Allow", "GET, DELETE")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})

	mux.HandleFunc("/api/notes/consumed", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", "POST")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		count := ns.markAllConsumed()
		writeJSON(w, http.StatusOK, map[string]any{"consumed": count})
	})
}
