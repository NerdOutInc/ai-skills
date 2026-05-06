package main

import (
	"crypto/rand"
	"crypto/subtle"
	"fmt"
	"math/big"
	"net"
	"net/http"
	"strings"
	"time"
)

const (
	pinCookieName = "ss_pin"
	pinHeaderName = "X-Status-Pin"
	pinQueryName  = "pin"
)

// generatePIN returns a 4-digit PIN as a string, e.g. "0427".
func generatePIN() (string, error) {
	n, err := rand.Int(rand.Reader, big.NewInt(10000))
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%04d", n.Int64()), nil
}

// isLocalhost reports whether the request originated from the loopback
// interface. The agent's own update/notes/status CLI calls hit 127.0.0.1
// and bypass auth.
func isLocalhost(r *http.Request) bool {
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		host = r.RemoteAddr
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

// presentedPIN reads the PIN from cookie, query string, or header.
// Cookie takes precedence so manual ?pin=... links don't get logged in
// referrers after the first hit.
func presentedPIN(r *http.Request) string {
	if c, err := r.Cookie(pinCookieName); err == nil {
		if v := strings.TrimSpace(c.Value); v != "" {
			return v
		}
	}
	if v := strings.TrimSpace(r.URL.Query().Get(pinQueryName)); v != "" {
		return v
	}
	return strings.TrimSpace(r.Header.Get(pinHeaderName))
}

// authWrap returns a handler that enforces the PIN. Localhost requests
// bypass auth. A correct ?pin=... query also sets a session cookie so the
// page's subsequent fetches authenticate without exposing the PIN in URLs.
// Failed checks incur a 250ms delay to slow brute force.
func authWrap(pin string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if isLocalhost(r) {
			next.ServeHTTP(w, r)
			return
		}

		got := presentedPIN(r)
		if got != "" && subtle.ConstantTimeCompare([]byte(got), []byte(pin)) == 1 {
			// If the PIN arrived via query, persist it as a cookie so
			// future requests don't have to carry it in the URL.
			if r.URL.Query().Get(pinQueryName) != "" {
				http.SetCookie(w, &http.Cookie{
					Name:     pinCookieName,
					Value:    pin,
					Path:     "/",
					HttpOnly: true,
					SameSite: http.SameSiteLaxMode,
					Expires:  time.Now().Add(7 * 24 * time.Hour),
				})
			}
			next.ServeHTTP(w, r)
			return
		}

		time.Sleep(250 * time.Millisecond)

		if strings.HasPrefix(r.URL.Path, "/api/") {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = fmt.Fprintln(w, `{"error":"pin required"}`)
			return
		}

		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = fmt.Fprint(w, pinRequiredHTML)
	})
}

const pinRequiredHTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PIN required</title>
<style>
  :root { color-scheme: dark; }
  body {
    margin: 0; padding: 24px;
    background: #0b0d10; color: #e7ecf2;
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    display: flex; min-height: 100vh; align-items: center; justify-content: center;
  }
  .card {
    background: #14181d; border: 1px solid #232a33; border-radius: 14px;
    padding: 24px; max-width: 360px; width: 100%;
  }
  h1 { margin: 0 0 6px; font-size: 18px; }
  p { color: #8a96a3; margin: 0 0 16px; font-size: 14px; }
  form { display: flex; gap: 8px; }
  input {
    flex: 1; font-size: 22px; letter-spacing: 6px; text-align: center;
    padding: 12px; border-radius: 8px; border: 1px solid #232a33;
    background: #1a1f26; color: #e7ecf2;
  }
  button {
    padding: 12px 16px; font-size: 16px; font-weight: 600;
    background: #5cc8ff; color: #0b0d10; border: 0; border-radius: 8px;
    cursor: pointer;
  }
  button:hover { filter: brightness(1.1); }
</style>
</head>
<body>
  <div class="card">
    <h1>PIN required</h1>
    <p>Enter the 4-digit PIN shown when the recording status server started.</p>
    <form onsubmit="event.preventDefault(); var p=document.getElementById('p').value.trim(); if(p) location='/?pin='+encodeURIComponent(p);">
      <input id="p" type="tel" inputmode="numeric" pattern="[0-9]*" maxlength="4" autofocus placeholder="••••">
      <button type="submit">Open</button>
    </form>
  </div>
</body>
</html>
`
