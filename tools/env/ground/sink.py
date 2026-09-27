#!/usr/bin/env python3
"""Local HTTP sink between Studio snippets and the ground tools (ENV-3).

Studio's MCP replies are too small for the probe data, so the snippets talk
HTTP to this instead (Studio allows localhost; the snippet turns
HttpService.HttpEnabled on for its own call):
  GET  /<file>  serves <serve_dir>/<file>   (probe row lists)
  POST /<file>  writes the body to <out_dir>/<file>   (probe results, harvests)

  python3 tools/env/ground/sink.py <out_dir> [serve_dir]   # port 34999, blocks
"""
OUT = sys.argv[1]
SERVE = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(n)
        name = os.path.basename(self.path.strip('/')) or 'post'
        with open(os.path.join(OUT, name), 'wb') as f:
            f.write(body)
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok %d' % len(body))
    def do_GET(self):
        name = os.path.basename(self.path.strip('/'))
        p = os.path.join(SERVE, name)
        if not os.path.isfile(p):
            self.send_response(404); self.end_headers(); return
        data = open(p, 'rb').read()
        self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self, *a): pass
http.server.HTTPServer(('127.0.0.1', 34999), H).serve_forever()
