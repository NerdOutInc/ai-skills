package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"html"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"
)

const (
	defaultPort = 8765
	maxLog      = 50
)

type LogEntry struct {
	At     time.Time `json:"at"`
	Phase  string    `json:"phase"`
	Action string    `json:"action"`
}

type Status struct {
	Phase     string     `json:"phase"`
	Project   string     `json:"project"`
	Action    string     `json:"action"`
	Note      string     `json:"note"`
	StartedAt *time.Time `json:"started_at,omitempty"`
	UpdatedAt time.Time  `json:"updated_at"`
	Log       []LogEntry `json:"log"`
}

type store struct {
	mu sync.RWMutex
	s  Status
}

func newStore() *store {
	return &store{
		s: Status{
			Phase:     "idle",
			UpdatedAt: time.Now(),
			Log:       []LogEntry{},
		},
	}
}

func (st *store) snapshot() Status {
	st.mu.RLock()
	defer st.mu.RUnlock()
	cp := st.s
	cp.Log = make([]LogEntry, len(st.s.Log))
	copy(cp.Log, st.s.Log)
	return cp
}

type updatePayload struct {
	Phase     *string `json:"phase,omitempty"`
	Project   *string `json:"project,omitempty"`
	Action    *string `json:"action,omitempty"`
	Note      *string `json:"note,omitempty"`
	ResetLog  bool    `json:"reset_log,omitempty"`
	ClearTime bool    `json:"clear_started_at,omitempty"`
}

func (st *store) apply(p updatePayload) Status {
	st.mu.Lock()
	defer st.mu.Unlock()

	now := time.Now()

	if p.ResetLog {
		st.s.Log = []LogEntry{}
	}
	if p.Phase != nil {
		newPhase := strings.ToLower(strings.TrimSpace(*p.Phase))
		if newPhase != "" {
			oldPhase := st.s.Phase
			st.s.Phase = newPhase
			if newPhase == "recording" && oldPhase != "recording" {
				t := now
				st.s.StartedAt = &t
			}
			if newPhase != "recording" && newPhase != "preparing" && p.ClearTime {
				st.s.StartedAt = nil
			}
		}
	}
	if p.Project != nil {
		st.s.Project = *p.Project
	}
	if p.Note != nil {
		st.s.Note = *p.Note
	}
	if p.Action != nil && strings.TrimSpace(*p.Action) != "" {
		st.s.Action = *p.Action
		st.s.Log = append(st.s.Log, LogEntry{
			At:     now,
			Phase:  st.s.Phase,
			Action: *p.Action,
		})
		if len(st.s.Log) > maxLog {
			st.s.Log = st.s.Log[len(st.s.Log)-maxLog:]
		}
	}
	if p.ClearTime && p.Phase == nil {
		st.s.StartedAt = nil
	}

	st.s.UpdatedAt = now
	cp := st.s
	cp.Log = make([]LogEntry, len(st.s.Log))
	copy(cp.Log, st.s.Log)
	return cp
}

// bonjourName returns the macOS Bonjour hostname (e.g. "BriansMac.local")
// using `scutil --get LocalHostName`. Falls back to os.Hostname() when scutil
// is unavailable. Returns an empty string if neither yields a usable name.
func bonjourName() string {
	if path, err := exec.LookPath("scutil"); err == nil {
		ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second)
		defer cancel()
		out, err := exec.CommandContext(ctx, path, "--get", "LocalHostName").Output()
		if err == nil {
			name := strings.TrimSpace(string(out))
			if name != "" {
				return name + ".local"
			}
		}
	}
	if h, err := os.Hostname(); err == nil {
		h = strings.TrimSpace(h)
		if h == "" || strings.EqualFold(h, "localhost") {
			return ""
		}
		if strings.Contains(h, ".") {
			return h
		}
		return h + ".local"
	}
	return ""
}

// preferredLANIP returns the most likely-correct LAN IPv4 to print in QR
// codes and announcements: the first private-range address (10/8, 172.16/12,
// 192.168/16). Falls back to the first non-private IPv4 if none is private.
func preferredLANIP(ips []string) string {
	if len(ips) == 0 {
		return ""
	}
	for _, s := range ips {
		ip := net.ParseIP(s)
		if ip != nil && ip.IsPrivate() {
			return s
		}
	}
	return ips[0]
}

func lanIPs() []string {
	out := []string{}
	ifaces, err := net.Interfaces()
	if err != nil {
		return out
	}
	for _, iface := range ifaces {
		if iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 {
			continue
		}
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		for _, a := range addrs {
			var ip net.IP
			switch v := a.(type) {
			case *net.IPNet:
				ip = v.IP
			case *net.IPAddr:
				ip = v.IP
			}
			if ip == nil || ip.IsLoopback() || ip.To4() == nil || ip.IsLinkLocalUnicast() {
				continue
			}
			out = append(out, ip.String())
		}
	}
	return out
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func runServer(port int, pinOverride, agentName string) error {
	st := newStore()
	ns := newNoteStore()

	pin := strings.TrimSpace(pinOverride)
	if pin == "" {
		p, err := generatePIN()
		if err != nil {
			return fmt.Errorf("generate pin: %w", err)
		}
		pin = p
	}

	agent := strings.TrimSpace(agentName)
	if agent == "" {
		agent = "the agent"
	}
	pageBytes := []byte(strings.NewReplacer(
		"{{AGENT}}", html.EscapeString(agent),
		"{{PIN}}", html.EscapeString(pin),
	).Replace(indexHTML))

	mux := http.NewServeMux()

	mux.HandleFunc("/api/status", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			writeJSON(w, http.StatusOK, st.snapshot())
		case http.MethodPost, http.MethodPut, http.MethodPatch:
			body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 64*1024))
			if err != nil {
				writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
				return
			}
			var p updatePayload
			if len(body) > 0 {
				if err := json.Unmarshal(body, &p); err != nil {
					writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json: " + err.Error()})
					return
				}
			}
			writeJSON(w, http.StatusOK, st.apply(p))
		default:
			w.Header().Set("Allow", "GET, POST")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})

	mux.HandleFunc("/api/lan", func(w http.ResponseWriter, r *http.Request) {
		ips := lanIPs()
		writeJSON(w, http.StatusOK, map[string]any{
			"ips":       ips,
			"bonjour":   bonjourName(),
			"port":      port,
			"preferred": preferredLANIP(ips),
			"agent":     agent,
		})
	})

	installNoteRoutes(mux, ns, st)

	mux.HandleFunc("/api/qr.png", func(w http.ResponseWriter, r *http.Request) {
		ips := lanIPs()
		preferred := preferredLANIP(ips)
		if preferred == "" {
			preferred = "127.0.0.1"
		}
		url := fmt.Sprintf("http://%s:%d/?pin=%s", preferred, port, pin)
		png, err := renderQRPNG(url, 320)
		if err != nil {
			http.Error(w, "qr error: "+err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "image/png")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = w.Write(png)
	})

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = w.Write(pageBytes)
	})

	addr := fmt.Sprintf("0.0.0.0:%d", port)
	srv := &http.Server{
		Addr:              addr,
		Handler:           authWrap(pin, mux),
		ReadHeaderTimeout: 5 * time.Second,
	}

	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return err
	}

	qrPath := writeStartupQR(port, pin)
	announceStartup(port, pin, agent, qrPath)

	return srv.Serve(ln)
}

// writeStartupQR renders the LAN-IP-with-PIN URL as a PNG and writes it to
// a stable temp path so chat agents can embed it via a markdown image link
// without making an HTTP request. Returns the file path on success, "" on
// any failure.
func writeStartupQR(port int, pin string) string {
	ips := lanIPs()
	preferred := preferredLANIP(ips)
	if preferred == "" {
		preferred = "127.0.0.1"
	}
	url := fmt.Sprintf("http://%s:%d/?pin=%s", preferred, port, pin)
	png, err := renderQRPNG(url, 480)
	if err != nil {
		return ""
	}
	f, err := os.CreateTemp("", fmt.Sprintf("screen-studio-status-qr-%d-%s-*.png", port, pin))
	if err != nil {
		return ""
	}
	path := f.Name()
	if _, err := f.Write(png); err != nil {
		_ = f.Close()
		_ = os.Remove(path)
		return ""
	}
	if err := f.Close(); err != nil {
		_ = os.Remove(path)
		return ""
	}
	return path
}

// announceStartup writes the human-facing block: PIN, URLs (with pin
// embedded), QR PNG file path (for chat embeds), and an ASCII QR fallback.
// Goes to stdout without log prefixes so the ASCII QR scans correctly when
// terminal users want to use it directly.
func announceStartup(port int, pin, agent, qrPath string) {
	ips := lanIPs()
	bonjour := bonjourName()
	preferred := preferredLANIP(ips)

	bonjourURL := ""
	if bonjour != "" {
		bonjourURL = fmt.Sprintf("http://%s:%d/?pin=%s", bonjour, port, pin)
	}
	lanURL := ""
	if preferred != "" {
		lanURL = fmt.Sprintf("http://%s:%d/?pin=%s", preferred, port, pin)
	}

	fmt.Println()
	fmt.Println("┌──────────────────────────────────────────")
	fmt.Println("│  Screen Studio recording status server")
	fmt.Println("├──────────────────────────────────────────")
	fmt.Printf("│  Agent:    %s\n", agent)
	fmt.Printf("│  PIN:      %s\n", pin)
	if bonjourURL != "" {
		fmt.Printf("│  Bonjour:  %s\n", bonjourURL)
	}
	if lanURL != "" {
		fmt.Printf("│  LAN IP:   %s\n", lanURL)
	}
	if bonjourURL == "" && lanURL == "" {
		fmt.Printf("│  Local:    http://127.0.0.1:%d/?pin=%s\n", port, pin)
	}
	if qrPath != "" {
		fmt.Printf("│  QR PNG:   %s\n", qrPath)
	}
	fmt.Println("└──────────────────────────────────────────")

	if lanURL != "" {
		fmt.Println()
		fmt.Println("ASCII QR (terminal use only — chat agents should embed the QR PNG):")
		fmt.Println()
		if qr := renderQR(lanURL); qr != "" {
			fmt.Print(qr)
		} else {
			fmt.Println("  (QR rendering failed; use the URL above)")
		}
		fmt.Println()
	}

	log.SetFlags(log.LstdFlags)
	log.Printf("listening on http://%s", fmt.Sprintf("0.0.0.0:%d", port))
}

func runUpdate(args []string) error {
	fs := flag.NewFlagSet("update", flag.ContinueOnError)
	host := fs.String("host", "127.0.0.1", "server host")
	port := fs.Int("port", defaultPort, "server port")
	phase := fs.String("phase", "", "phase: idle, preparing, recording, stopped, error")
	project := fs.String("project", "", "project name")
	action := fs.String("action", "", "current action description")
	note := fs.String("note", "", "free-form note")
	resetLog := fs.Bool("reset-log", false, "clear the action log before applying")
	clearTime := fs.Bool("clear-started-at", false, "clear the recording start time")
	timeout := fs.Duration("timeout", 3*time.Second, "request timeout")

	if err := fs.Parse(args); err != nil {
		return err
	}

	payload := map[string]any{}
	if isFlagSet(fs, "phase") {
		payload["phase"] = *phase
	}
	if isFlagSet(fs, "project") {
		payload["project"] = *project
	}
	if isFlagSet(fs, "action") {
		payload["action"] = *action
	}
	if isFlagSet(fs, "note") {
		payload["note"] = *note
	}
	if *resetLog {
		payload["reset_log"] = true
	}
	if *clearTime {
		payload["clear_started_at"] = true
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	url := fmt.Sprintf("http://%s:%d/api/status", *host, *port)
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: *timeout}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("update failed: %w", err)
	}
	defer resp.Body.Close()
	rb, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return fmt.Errorf("server returned %s: %s", resp.Status, string(rb))
	}
	fmt.Println(string(rb))
	return nil
}

func isFlagSet(fs *flag.FlagSet, name string) bool {
	set := false
	fs.Visit(func(f *flag.Flag) {
		if f.Name == name {
			set = true
		}
	})
	return set
}

func runStatus(args []string) error {
	fs := flag.NewFlagSet("status", flag.ContinueOnError)
	host := fs.String("host", "127.0.0.1", "server host")
	port := fs.Int("port", defaultPort, "server port")
	timeout := fs.Duration("timeout", 3*time.Second, "request timeout")
	if err := fs.Parse(args); err != nil {
		return err
	}
	url := fmt.Sprintf("http://%s:%d/api/status", *host, *port)
	client := &http.Client{Timeout: *timeout}
	resp, err := client.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	rb, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return fmt.Errorf("server returned %s: %s", resp.Status, string(rb))
	}
	fmt.Println(string(rb))
	return nil
}

// runNotes fetches notes from a running server and prints them as JSON.
//
//	--since-id N   return notes with id strictly greater than N
//	--all          include notes the agent has already marked consumed
//	--clear        after listing, mark all returned notes as consumed
//	               (preserves them on the server so the page can display
//	               "seen by agent" — does NOT delete)
//	--purge        after listing, hard-delete all notes from the server
//	               (use only when starting a totally fresh session)
func runNotes(args []string) error {
	fs := flag.NewFlagSet("notes", flag.ContinueOnError)
	host := fs.String("host", "127.0.0.1", "server host")
	port := fs.Int("port", defaultPort, "server port")
	sinceID := fs.Int("since-id", 0, "return notes with id strictly greater than this")
	all := fs.Bool("all", false, "include already-consumed notes in the listing")
	clear := fs.Bool("clear", false, "after listing, mark all notes as seen (POST /api/notes/consumed)")
	purge := fs.Bool("purge", false, "after listing, hard-delete all notes from the server")
	timeout := fs.Duration("timeout", 3*time.Second, "request timeout")
	if err := fs.Parse(args); err != nil {
		return err
	}

	statusQ := "open"
	if *all || *clear || *purge {
		// When the agent is about to consume/delete, show what it's
		// taking (consumed history included) so the chat output is
		// the full picture.
		statusQ = "all"
	}
	url := fmt.Sprintf("http://%s:%d/api/notes?since_id=%d&status=%s", *host, *port, *sinceID, statusQ)
	client := &http.Client{Timeout: *timeout}
	resp, err := client.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	rb, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return fmt.Errorf("server returned %s: %s", resp.Status, string(rb))
	}
	fmt.Println(string(rb))

	if *clear {
		req, err := http.NewRequest(http.MethodPost,
			fmt.Sprintf("http://%s:%d/api/notes/consumed", *host, *port), nil)
		if err != nil {
			return err
		}
		dresp, err := client.Do(req)
		if err != nil {
			return err
		}
		_ = dresp.Body.Close()
	}
	if *purge {
		req, err := http.NewRequest(http.MethodDelete,
			fmt.Sprintf("http://%s:%d/api/notes", *host, *port), nil)
		if err != nil {
			return err
		}
		dresp, err := client.Do(req)
		if err != nil {
			return err
		}
		_ = dresp.Body.Close()
	}
	return nil
}

func usage() {
	fmt.Fprintf(os.Stderr, `screen-studio status server

Usage:
  status-server [serve] [--port N] [--pin XXXX] [--agent NAME]
                                                  start HTTP server (default port %d)
  status-server update [flags]                    POST a status update to a running server
  status-server status [flags]                    GET the current status JSON
  status-server notes  [flags]                    GET pending notes from the page

Update flags:
  --host HOST                server host (default 127.0.0.1)
  --port N                   server port (default %d)
  --phase PHASE              idle | preparing | recording | stopped | error
  --project NAME             project name
  --action TEXT              current action (also appended to log)
  --note TEXT                free-form status note (different from page notes)
  --reset-log                clear the action log before applying
  --clear-started-at         clear the recording start time
  --timeout DURATION         request timeout (default 3s)

Notes flags:
  --since-id N               only return notes with id > N
  --all                      include already-consumed notes in the listing
  --clear                    after listing, mark all as seen (default for debriefs;
                             preserves notes on server so the page shows "seen")
  --purge                    after listing, hard-delete all notes (use sparingly)
  --host HOST                server host (default 127.0.0.1)
  --port N                   server port (default %d)
  --timeout DURATION         request timeout (default 3s)

Examples:
  status-server                                                # serve, random PIN
  status-server --port 9000                                    # serve on 9000
  status-server --pin 1234                                     # serve with fixed PIN (dev)
  status-server --agent Claude                                 # page UI says "Claude" instead of "the agent"
  status-server update --phase recording --action "Started"
  status-server update --action "Clicked Submit"
  status-server update --phase stopped --action "Stopped" --clear-started-at
  status-server notes --clear                                  # debrief: read all + clear
`, defaultPort, defaultPort, defaultPort)
}

func parseServeFlags(args []string) (port int, pin, agent string, err error) {
	fs := flag.NewFlagSet("serve", flag.ContinueOnError)
	pPort := fs.Int("port", defaultPort, "listen port")
	pPin := fs.String("pin", "", "override the random 4-digit PIN (4 digits)")
	pAgent := fs.String("agent", "", "agent name shown in the page UI (e.g. Codex, Claude). Default: \"the agent\"")
	if err := fs.Parse(args); err != nil {
		return 0, "", "", err
	}
	return *pPort, *pPin, *pAgent, nil
}

func main() {
	log.SetFlags(log.LstdFlags)

	args := os.Args[1:]
	if len(args) == 0 {
		if err := runServer(defaultPort, "", ""); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatal(err)
		}
		return
	}

	switch args[0] {
	case "serve":
		port, pin, agent, err := parseServeFlags(args[1:])
		if err != nil {
			os.Exit(2)
		}
		if err := runServer(port, pin, agent); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatal(err)
		}
	case "update":
		if err := runUpdate(args[1:]); err != nil {
			fmt.Fprintln(os.Stderr, "error:", err)
			os.Exit(1)
		}
	case "status":
		if err := runStatus(args[1:]); err != nil {
			fmt.Fprintln(os.Stderr, "error:", err)
			os.Exit(1)
		}
	case "notes":
		if err := runNotes(args[1:]); err != nil {
			fmt.Fprintln(os.Stderr, "error:", err)
			os.Exit(1)
		}
	case "-h", "--help", "help":
		usage()
	default:
		// Allow `status-server --port 9000 --pin 1234 --agent Claude` shorthand for serve.
		if strings.HasPrefix(args[0], "-") {
			port, pin, agent, err := parseServeFlags(args)
			if err != nil {
				os.Exit(2)
			}
			if err := runServer(port, pin, agent); err != nil && !errors.Is(err, http.ErrServerClosed) {
				log.Fatal(err)
			}
			return
		}
		fmt.Fprintf(os.Stderr, "unknown command: %s\n\n", args[0])
		usage()
		os.Exit(2)
	}
}
