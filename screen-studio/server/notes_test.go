package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

// assertNoKey decodes raw JSON into a map and fails the test if the named
// top-level key is present. Use this rather than substring-matching on the
// raw body so the assertion stays clear about its intent (key absence) and
// can't be confused by string values that happen to contain the key name.
func assertNoKey(t *testing.T, raw []byte, key string) {
	t.Helper()
	var top map[string]json.RawMessage
	if err := json.Unmarshal(raw, &top); err != nil {
		t.Fatalf("decode body for key-absence check: %v", err)
	}
	if _, ok := top[key]; ok {
		t.Fatalf("body unexpectedly contains key %q: %s", key, string(raw))
	}
}

// postNote is a tiny helper that submits a note to the test mux the same
// way the page does, returning the assigned ID.
func postNote(t *testing.T, mux *http.ServeMux, text string) int {
	t.Helper()
	body, _ := json.Marshal(map[string]string{"text": text})
	r := httptest.NewRequest(http.MethodPost, "/api/note", bytes.NewReader(body))
	r.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, r)
	if w.Code != http.StatusOK {
		t.Fatalf("POST /api/note: status = %d, body = %s", w.Code, w.Body.String())
	}
	var n Note
	if err := json.Unmarshal(w.Body.Bytes(), &n); err != nil {
		t.Fatalf("decode note: %v", err)
	}
	return n.ID
}

// postUpdate runs an update against the test mux and returns the parsed
// updateResponse plus the raw JSON (the latter is used to assert that
// `notes` is omitted, not just empty).
func postUpdate(t *testing.T, mux *http.ServeMux, action string) (updateResponse, []byte) {
	t.Helper()
	body, _ := json.Marshal(map[string]any{"action": action})
	r := httptest.NewRequest(http.MethodPost, "/api/status", bytes.NewReader(body))
	r.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, r)
	if w.Code != http.StatusOK {
		t.Fatalf("POST /api/status: status = %d, body = %s", w.Code, w.Body.String())
	}
	raw := append([]byte(nil), w.Body.Bytes()...)
	var resp updateResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("decode updateResponse: %v", err)
	}
	return resp, raw
}

// newTestMux wires the same routes the production server installs, but
// without the page handler, auth wrapper, or listener — enough to exercise
// the update-consumes-notes flow end-to-end via httptest.
func newTestMux() *http.ServeMux {
	st := newStore()
	ns := newNoteStore()
	mux := http.NewServeMux()
	installStatusRoute(mux, st, ns)
	installNoteRoutes(mux, ns, st)
	return mux
}

func TestUpdateReturnsAndConsumesUnreadNotes(t *testing.T) {
	mux := newTestMux()

	id1 := postNote(t, mux, "hide codex")
	id2 := postNote(t, mux, "stop, broken")

	resp, _ := postUpdate(t, mux, "Verifying note delivery")

	if len(resp.Notes) != 2 {
		t.Fatalf("notes returned = %d, want 2", len(resp.Notes))
	}
	gotIDs := []int{resp.Notes[0].ID, resp.Notes[1].ID}
	if !((gotIDs[0] == id1 && gotIDs[1] == id2) || (gotIDs[0] == id2 && gotIDs[1] == id1)) {
		t.Fatalf("returned ids = %v, want %v in some order", gotIDs, []int{id1, id2})
	}
	for _, n := range resp.Notes {
		if n.ConsumedAt == nil {
			t.Fatalf("note id=%d returned without ConsumedAt", n.ID)
		}
	}
}

func TestSecondUpdateOmitsAlreadyConsumedNotes(t *testing.T) {
	mux := newTestMux()

	postNote(t, mux, "hide codex")
	postNote(t, mux, "stop, broken")

	if resp, _ := postUpdate(t, mux, "first"); len(resp.Notes) != 2 {
		t.Fatalf("first update returned %d notes, want 2", len(resp.Notes))
	}

	resp, raw := postUpdate(t, mux, "second")
	if len(resp.Notes) != 0 {
		t.Fatalf("second update returned %d notes, want 0", len(resp.Notes))
	}
	assertNoKey(t, raw, "notes")
}

func TestGetStatusDoesNotReturnNotes(t *testing.T) {
	mux := newTestMux()
	postNote(t, mux, "hide codex")

	r := httptest.NewRequest(http.MethodGet, "/api/status", nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, r)
	if w.Code != http.StatusOK {
		t.Fatalf("GET /api/status: status = %d", w.Code)
	}
	assertNoKey(t, w.Body.Bytes(), "notes")

	resp, _ := postUpdate(t, mux, "consume")
	if len(resp.Notes) != 1 {
		t.Fatalf("update consumed %d notes, want 1", len(resp.Notes))
	}
}

func TestUpdateAfterConsumeReturnsOnlyNewNote(t *testing.T) {
	mux := newTestMux()

	postNote(t, mux, "first")
	if resp, _ := postUpdate(t, mux, "consume first"); len(resp.Notes) != 1 {
		t.Fatalf("first update returned %d notes, want 1", len(resp.Notes))
	}

	freshID := postNote(t, mux, "fresh")
	resp, _ := postUpdate(t, mux, "consume fresh")
	if len(resp.Notes) != 1 || resp.Notes[0].ID != freshID {
		t.Fatalf("expected only fresh note (id=%d), got %+v", freshID, resp.Notes)
	}
	if resp.Notes[0].Text != "fresh" {
		t.Fatalf("returned note text = %q, want %q", resp.Notes[0].Text, "fresh")
	}
}
