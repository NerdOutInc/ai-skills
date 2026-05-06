package main

import (
	"strings"

	qrcode "github.com/skip2/go-qrcode"
)

// renderQRPNG returns a PNG-encoded QR code at the given square size.
func renderQRPNG(data string, size int) ([]byte, error) {
	q, err := qrcode.New(data, qrcode.Medium)
	if err != nil {
		return nil, err
	}
	return q.PNG(size)
}

// renderQR returns a half-block ASCII QR code encoding `data`. Each
// terminal line covers two QR rows so the result roughly preserves square
// aspect on standard monospace fonts. A 2-module quiet zone is added on
// every side. Returns an empty string if encoding fails.
func renderQR(data string) string {
	q, err := qrcode.New(data, qrcode.Medium)
	if err != nil {
		return ""
	}
	q.DisableBorder = true
	bm := q.Bitmap()
	if len(bm) == 0 {
		return ""
	}

	const quiet = 2
	rows := len(bm)
	cols := len(bm[0])

	// Pad with a 2-module quiet zone (false = light) on every side.
	padded := make([][]bool, rows+quiet*2)
	for i := range padded {
		padded[i] = make([]bool, cols+quiet*2)
	}
	for y := 0; y < rows; y++ {
		for x := 0; x < cols; x++ {
			padded[y+quiet][x+quiet] = bm[y][x]
		}
	}

	prows := len(padded)
	pcols := len(padded[0])

	var b strings.Builder
	for y := 0; y < prows; y += 2 {
		for x := 0; x < pcols; x++ {
			top := padded[y][x]
			bot := false
			if y+1 < prows {
				bot = padded[y+1][x]
			}
			switch {
			case top && bot:
				b.WriteString("█")
			case top && !bot:
				b.WriteString("▀")
			case !top && bot:
				b.WriteString("▄")
			default:
				b.WriteString(" ")
			}
		}
		b.WriteString("\n")
	}
	return b.String()
}
