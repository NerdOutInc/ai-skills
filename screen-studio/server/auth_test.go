package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestPresentedPINQueryOverridesStaleCookie(t *testing.T) {
	r := httptest.NewRequest(http.MethodGet, "/?pin=2222", nil)
	r.AddCookie(&http.Cookie{Name: pinCookieName, Value: "1111"})

	if got := presentedPIN(r); got != "2222" {
		t.Fatalf("presentedPIN() = %q, want query PIN", got)
	}
}

func TestCorrectQueryPINReplacesStaleCookie(t *testing.T) {
	next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNoContent)
	})
	r := httptest.NewRequest(http.MethodGet, "/?pin=2222", nil)
	r.RemoteAddr = "192.168.1.50:12345"
	r.AddCookie(&http.Cookie{Name: pinCookieName, Value: "1111"})
	w := httptest.NewRecorder()

	authWrap("2222", next).ServeHTTP(w, r)

	if w.Code != http.StatusNoContent {
		t.Fatalf("status = %d, want %d", w.Code, http.StatusNoContent)
	}
	cookies := w.Result().Cookies()
	if len(cookies) != 1 {
		t.Fatalf("set cookies = %d, want 1", len(cookies))
	}
	if cookies[0].Name != pinCookieName || cookies[0].Value != "2222" {
		t.Fatalf("cookie = %s=%q, want %s=2222", cookies[0].Name, cookies[0].Value, pinCookieName)
	}
}

func TestWrongQueryPINExpiresStaleCookie(t *testing.T) {
	next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Fatal("next should not be called")
	})
	r := httptest.NewRequest(http.MethodGet, "/?pin=3333", nil)
	r.RemoteAddr = "192.168.1.50:12345"
	r.AddCookie(&http.Cookie{Name: pinCookieName, Value: "1111"})
	w := httptest.NewRecorder()

	authWrap("2222", next).ServeHTTP(w, r)

	if w.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", w.Code, http.StatusUnauthorized)
	}
	var expired bool
	for _, c := range w.Result().Cookies() {
		if c.Name == pinCookieName && c.MaxAge < 0 {
			expired = true
		}
	}
	if !expired {
		t.Fatal("wrong query PIN did not expire stale pin cookie")
	}
}

func TestStartupQRPathIsUniquePerPIN(t *testing.T) {
	first := writeStartupQR(8765, "1111")
	second := writeStartupQR(8765, "2222")
	if first == "" || second == "" {
		t.Fatalf("writeStartupQR returned empty path: %q %q", first, second)
	}
	if first == second {
		t.Fatalf("writeStartupQR reused path %q", first)
	}
	if !strings.Contains(first, "1111") || !strings.Contains(second, "2222") {
		t.Fatalf("QR paths do not include run PINs: %q %q", first, second)
	}
}
