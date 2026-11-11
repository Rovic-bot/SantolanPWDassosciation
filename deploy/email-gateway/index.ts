// Deploy only after replacing the placeholder with SHA-256 of a random
// server-only token (at least 48 random bytes). No token or Gmail credential
// belongs in this source. JWT verification is replaced by this private token.
import nodemailer from "npm:nodemailer@10.5.0";
import { Buffer } from "node:buffer";

const TOKEN_HASH = "__DEPLOYMENT_TOKEN_SHA256__";
const reply = (body: object, status = 200) => Response.json(body, {
  status, headers: { "Cache-Control": "no-store" },
});

Deno.serve(async (req: Request) => {
  const auth = req.headers.get("authorization") || "";
  if (!auth.startsWith("Bearer ") || auth.length > 200) return reply({ok:false},401);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(auth.slice(7)));
  const actual = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2,"0")).join("");
  if (actual !== TOKEN_HASH) return reply({ok:false},401);
  if (req.method !== "POST") return reply({ok:false},405);
  let transport;
  try {
    // Bound the stream as well as Content-Length, including chunked requests.
    const reader = req.body?.getReader();
    if (!reader) return reply({ok:false},400);
    const chunks: Uint8Array[] = []; let size=0;
    for (;;) {
      const {value, done} = await reader.read();
      if (done) break;
      size += value.length;
      if (size > 17*1024*1024) { await reader.cancel(); return reply({ok:false},413); }
      chunks.push(value);
    }
    const combined = new Uint8Array(size); let offset=0;
    for (const chunk of chunks) { combined.set(chunk,offset); offset+=chunk.length; }
    const body = JSON.parse(new TextDecoder().decode(combined));
    const email = /^[^\s<>\r\n@]+@[^\s<>\r\n@]+\.[^\s<>\r\n@]+$/;
    if (!email.test(body.username) || typeof body.password !== "string" ||
        body.password.length > 200 || !["verify","send"].includes(body.action)) return reply({ok:false},400);
    transport = nodemailer.createTransport({host:"smtp.gmail.com",port:465,secure:true,
      auth:{user:body.username,pass:body.password},pool:false,logger:false,debug:false,
      connectionTimeout:12000,greetingTimeout:12000,socketTimeout:25000,
      tls:{rejectUnauthorized:true},disableFileAccess:true,disableUrlAccess:true});
    if (body.action === "verify") { await transport.verify(); return reply({ok:true}); }
    if (body.sender !== body.username || !Array.isArray(body.recipients) ||
        body.recipients.length < 1 || body.recipients.length > 50 ||
        body.recipients.some((e:unknown)=>typeof e!=="string" || !email.test(e)) ||
        typeof body.raw !== "string" || body.raw.length > 16*1024*1024) return reply({ok:false},400);
    const raw = Buffer.from(body.raw, "base64");
    const result = await transport.sendMail({envelope:{from:body.username,to:body.recipients},raw,
      disableFileAccess:true,disableUrlAccess:true});
    if (!result.accepted?.length) return reply({ok:false,error:"rejected"},422);
    return reply({ok:true});
  } catch (error) {
    // Never log or return SMTP responses, recipient addresses or credentials.
    const e = error as {code?:string;responseCode?:number};
    if (e.code === "EAUTH") return reply({ok:false,error:"authentication"},422);
    if (e.responseCode && e.responseCode >= 400) return reply({ok:false,error:"rejected"},422);
    return reply({ok:false,error:"unconfirmed"},502);
  } finally { transport?.close(); }
});
