"use client";

import React, { useEffect, useState, useRef } from "react";

export default function Home() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [navScrolled, setNavScrolled] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [activeStep, setActiveStep] = useState(0);
  const [tilt, setTilt] = useState<{ x: number; y: number }>({ x: -10, y: 4 });
  const [isHoveringPhone, setIsHoveringPhone] = useState(false);

  const phoneRef = useRef<HTMLDivElement>(null);
  const step0Ref = useRef<HTMLDivElement>(null);
  const step1Ref = useRef<HTMLDivElement>(null);
  const step2Ref = useRef<HTMLDivElement>(null);
  const statementRef = useRef<HTMLElement>(null);
  const rolesRef = useRef<HTMLElement>(null);
  const bandRef = useRef<HTMLDivElement>(null);

  const [statementInView, setStatementInView] = useState(false);
  const [rolesInView, setRolesInView] = useState(false);
  const [bandInView, setBandInView] = useState(false);

  // Initialize theme from DOM attribute or localStorage
  useEffect(() => {
    try {
      const current = document.documentElement.getAttribute("data-theme") as
        | "light"
        | "dark"
        | null;
      if (current) {
        setTheme(current);
      } else {
        const saved = localStorage.getItem("ll-theme") as
          | "light"
          | "dark"
          | null;
        if (
          saved === "dark" ||
          (!saved && window.matchMedia("(prefers-color-scheme: dark)").matches)
        ) {
          setTheme("dark");
          document.documentElement.setAttribute("data-theme", "dark");
        } else {
          setTheme("light");
          document.documentElement.setAttribute("data-theme", "light");
        }
      }
    } catch {}
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("ll-theme", next);
    } catch {}
  };

  // Scroll tracking for progress bar and nav shadow
  useEffect(() => {
    let ticking = false;
    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const y = window.scrollY;
          const max =
            document.documentElement.scrollHeight - window.innerHeight;
          setScrollProgress(max > 0 ? y / max : 0);
          setNavScrolled(y > 8);
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Intersection observers for storytelling steps & sections
  useEffect(() => {
    const stepRefs = [step0Ref.current, step1Ref.current, step2Ref.current];
    const stepObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const index = Number(entry.target.getAttribute("data-step"));
            if (!isNaN(index)) {
              setActiveStep(index);
            }
          }
        });
      },
      { rootMargin: "-40% 0px -40% 0px" }
    );

    stepRefs.forEach((el) => {
      if (el) stepObserver.observe(el);
    });

    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            if (entry.target === statementRef.current) setStatementInView(true);
            if (entry.target === rolesRef.current) setRolesInView(true);
            if (entry.target === bandRef.current) setBandInView(true);
          }
        });
      },
      { threshold: 0.15 }
    );

    if (statementRef.current) revealObserver.observe(statementRef.current);
    if (rolesRef.current) revealObserver.observe(rolesRef.current);
    if (bandRef.current) revealObserver.observe(bandRef.current);

    return () => {
      stepObserver.disconnect();
      revealObserver.disconnect();
    };
  }, []);

  // 3D tilt tracking for hero phone
  const handleStagePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!window.matchMedia("(hover: hover)").matches) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    setTilt({
      x: Number((x * 16).toFixed(2)),
      y: Number((-y * 12).toFixed(2)),
    });
    setIsHoveringPhone(true);
  };

  const handleStagePointerLeave = () => {
    setIsHoveringPhone(false);
    setTilt({ x: -10, y: 4 });
  };

  // Matrix log lines for callout band
  const matrixLogs = [
    "POST transfer · key 9f2a… · 201",
    "replay 9f2a… · 200 · same result",
    "withdraw ₹48,000 · refused",
    "Σ balances = Σ external ✓",
    "POST deposit · key c71e… · 201",
    "entry #1043 · hash e90d",
    "edit attempt · rejected",
    "reconcile · 0 difference",
  ];

  return (
    <>
      {/* Top scroll progress indicator */}
      <div
        className="prog"
        style={{ transform: `scaleX(${scrollProgress})` }}
        aria-hidden="true"
      />

      {/* Sticky Navigation */}
      <nav className={navScrolled ? "s" : ""}>
        <div className="wrap">
          <a className="logo" href="#top">
            LedgerLine
          </a>

          <div className="links">
            <a href="#how">How it works</a>
            <a href="#statement">Statement</a>
            <a href="#roles">Roles</a>
          </div>

          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <button
              className="tg"
              onClick={toggleTheme}
              aria-label="Toggle theme"
              title="Toggle theme"
            >
              {/* Sun icon */}
              <svg
                className="su"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              >
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
              </svg>
              {/* Moon icon */}
              <svg
                className="mo"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinejoin="round"
              >
                <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
              </svg>
            </button>

            <a className="btn" href="#statement">
              Open app
            </a>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="hero" id="top">
        <div className="wrap">
          <div>
            <h1>
              <span className="ln">
                <span>Money that</span>
              </span>
              <span className="ln">
                <span>
                  <em>proves</em> itself.
                </span>
              </span>
            </h1>

            <p className="lead">
              Move money between accounts without ever creating it, losing it, or
              paying twice, and keep a record no one can quietly edit.
            </p>

            <div className="cta">
              <a className="btn" href="#how">
                See how it works
              </a>
              <a className="btn o" href="#statement">
                View a statement
              </a>
            </div>
          </div>

          {/* Interactive 3D Phone Stage */}
          <div
            className="stage"
            onPointerMove={handleStagePointerMove}
            onPointerLeave={handleStagePointerLeave}
          >
            <div
              className="phone"
              ref={phoneRef}
              style={{
                transform: `rotateY(${tilt.x}deg) rotateX(${tilt.y}deg)`,
                transition: isHoveringPhone
                  ? "transform 0.1s ease-out"
                  : "transform 0.5s ease-out",
              }}
            >
              <div className="screen">
                <div className="scr on">
                  <small>Operating account · INR</small>
                  <div className="big mono">₹1,24,580</div>

                  <div className="acts">
                    <span>Deposit</span>
                    <span>Withdraw</span>
                    <span>Transfer</span>
                  </div>

                  <div className="it">
                    <div>
                      Vendor A
                      <small>Transfer · key 9f2a…</small>
                    </div>
                    <div className="neg mono">−₹12,000</div>
                  </div>

                  <div className="it">
                    <div>
                      Customer receipt
                      <small>Deposit · key c71e…</small>
                    </div>
                    <div className="pos mono">+₹36,580</div>
                  </div>

                  <div className="it">
                    <div>
                      Payroll batch
                      <small>Transfer · key 4b08…</small>
                    </div>
                    <div className="neg mono">−₹2,40,000</div>
                  </div>
                </div>
              </div>

              {/* 3D Floating Toast */}
              <div className="toast">
                <b>Retry detected</b>
                <br />
                <span style={{ color: "var(--mut)" }}>
                  Same key. No money moved.
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Interactive Story Section */}
      <section className="story" id="how">
        <div className="wrap">
          {/* Scrollable Story Steps */}
          <div className="steps">
            {/* Step 0 */}
            <div
              className={`st ${activeStep === 0 ? "on" : ""}`}
              ref={step0Ref}
              data-step="0"
              onClick={() => setActiveStep(0)}
            >
              <span className="n">01 — BOOKS BALANCE</span>
              <h3>Every rupee has a place.</h3>
              <p>
                Each transfer posts a debit and a credit in a single
                transaction. If one fails, both do.
              </p>
            </div>

            {/* Step 1 */}
            <div
              className={`st ${activeStep === 1 ? "on" : ""}`}
              ref={step1Ref}
              data-step="1"
              onClick={() => setActiveStep(1)}
            >
              <span className="n">02 — EXACTLY ONCE</span>
              <h3>Retry it. Nothing moves.</h3>
              <p>
                Every request carries a key. A replay returns the first result
                and is recorded as a duplicate.
              </p>
            </div>

            {/* Step 2 */}
            <div
              className={`st ${activeStep === 2 ? "on" : ""}`}
              ref={step2Ref}
              data-step="2"
              onClick={() => setActiveStep(2)}
            >
              <span className="n">03 — PROVABLE</span>
              <h3>A record that can’t be edited.</h3>
              <p>
                Posted and refused attempts are appended, never changed, each
                with a running balance and an initiator.
              </p>
            </div>
          </div>

          {/* Sticky Phone Mockup syncing with active step */}
          <div className="pin">
            <div className="stage">
              <div className="phone">
                <div className="screen">
                  {/* Screen 0 */}
                  <div className={`scr ${activeStep === 0 ? "on" : ""}`}>
                    <small>Transfer</small>
                    <div className="big mono">₹12,000</div>
                    <div className="it">
                      <div>
                        From<small>Operating</small>
                      </div>
                      <div className="mono">₹1,36,580</div>
                    </div>
                    <div className="it">
                      <div>
                        To<small>Vendor A</small>
                      </div>
                      <div className="mono">₹0</div>
                    </div>
                    <div className="note">
                      Debit and credit post together. Total balance unchanged.
                    </div>
                  </div>

                  {/* Screen 1 */}
                  <div className={`scr ${activeStep === 1 ? "on" : ""}`}>
                    <small>Activity</small>
                    <div className="big">Duplicate</div>
                    <div className="it">
                      <div>
                        Transfer to Vendor A<small className="mono">key 9f2a…</small>
                      </div>
                      <div className="neg mono">
                        −₹12,000<span className="chip">Posted</span>
                      </div>
                    </div>
                    <div className="it">
                      <div>
                        Same request, retried<small className="mono">key 9f2a…</small>
                      </div>
                      <div className="mono">
                        ₹0<span className="chip b">Duplicate</span>
                      </div>
                    </div>
                    <div className="note">
                      Returned the first result. No money moved.
                    </div>
                  </div>

                  {/* Screen 2 */}
                  <div className={`scr ${activeStep === 2 ? "on" : ""}`}>
                    <small>Statement</small>
                    <div className="big mono">₹1,24,580</div>
                    <div className="it">
                      <div>
                        Transfer out<small>priya · 10:42</small>
                      </div>
                      <div className="mono">1,24,580</div>
                    </div>
                    <div className="it">
                      <div>
                        Withdrawal<span className="chip b">Refused</span>
                        <small>raj · insufficient funds</small>
                      </div>
                      <div className="mono">1,36,580</div>
                    </div>
                    <div className="it">
                      <div>
                        Deposit<small>admin · 10:31</small>
                      </div>
                      <div className="mono">1,36,580</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Statement / Source of Truth Section */}
      <section id="statement" ref={statementRef}>
        <div className="wrap">
          <h2 className={`sp ${statementInView ? "in" : ""}`}>
            <span className="w">
              <span style={{ transitionDelay: "0ms" }}>The</span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "70ms" }}>statement</span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "140ms" }}>is</span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "210ms" }}>the</span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "280ms" }}>
                <em>source</em>
              </span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "350ms" }}>
                <em>of</em>
              </span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "420ms" }}>
                <em>truth.</em>
              </span>
            </span>
          </h2>

          <p className={`sub rv ${statementInView ? "in" : ""}`}>
            Every debit, credit and refusal, with the balance after it and who
            initiated it.
          </p>

          <div className={`led ${statementInView ? "in" : ""}`}>
            <div className="row h">
              <span>Entry</span>
              <span className="r">Amount</span>
              <span className="r x">Balance</span>
              <span className="r x">Initiated by</span>
            </div>

            <div className="row">
              <div>
                Transfer to Vendor A
                <small className="mono">key 9f2a…</small>
              </div>
              <div className="r neg mono">−₹12,000</div>
              <div className="r x mono">₹1,24,580</div>
              <div className="r x">priya@acme</div>
            </div>

            <div className="row">
              <div>
                Transfer to Vendor A <span className="chip b">Duplicate</span>
                <small className="mono">
                  key 9f2a… · first result returned
                </small>
              </div>
              <div className="r mono">₹0</div>
              <div className="r x mono">₹1,24,580</div>
              <div className="r x">priya@acme</div>
            </div>

            <div className="row">
              <div>
                Withdrawal <span className="chip b">Refused</span>
                <small className="mono">insufficient funds</small>
              </div>
              <div className="r mono">₹0</div>
              <div className="r x mono">₹1,36,580</div>
              <div className="r x">raj@acme</div>
            </div>

            <div className="row">
              <div>
                Deposit · customer receipt
                <small className="mono">key c71e…</small>
              </div>
              <div className="r pos mono">+₹36,580</div>
              <div className="r x mono">₹1,36,580</div>
              <div className="r x">admin</div>
            </div>
          </div>
        </div>
      </section>

      {/* Roles Section */}
      <section id="roles" ref={rolesRef} style={{ paddingTop: "20px" }}>
        <div className="wrap">
          <h2 className={`sp ${rolesInView ? "in" : ""}`}>
            <span className="w">
              <span style={{ transitionDelay: "0ms" }}>Three</span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "70ms" }}>roles.</span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "140ms" }}>
                <em>Clear</em>
              </span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "210ms" }}>
                <em>limits.</em>
              </span>
            </span>
          </h2>

          <div className="roles">
            {/* Role 1: Admin */}
            <div className={`rc rv ${rolesInView ? "in" : ""}`}>
              <div className="viz">
                <small>Accounts</small>
                <div className="vr">
                  <span>Operating</span>
                  <span className="mono">₹1,24,580</span>
                </div>
                <div className="vr">
                  <span>Payroll</span>
                  <span className="mono">₹8,40,000</span>
                </div>
                <div className="vr">
                  <span>
                    Vendors <span className="chip b pl">Flagged</span>
                  </span>
                  <span className="mono">₹62,300</span>
                </div>
                <small>Daily limit · ₹5,00,000</small>
                <div className="bar">
                  <i />
                </div>
              </div>

              <span className="k" style={{ display: "block", marginTop: "22px" }}>
                ADMIN
              </span>
              <h3 style={{ marginTop: "8px" }}>Operate</h3>
              <p>Create accounts, assign holders and review flagged activity.</p>
            </div>

            {/* Role 2: Account Holder */}
            <div className={`rc rv ${rolesInView ? "in" : ""}`}>
              <div className="viz">
                <small>Transfer</small>
                <div className="typ mono">₹12,000</div>
                <div className="flow">
                  <span>Operating</span>
                  <i />
                  <span>Vendor A</span>
                </div>
                <div className="send">
                  <b className="s1">Send</b>
                  <b className="s2">✓ Posted</b>
                </div>
              </div>

              <span className="k" style={{ display: "block", marginTop: "22px" }}>
                ACCOUNT HOLDER
              </span>
              <h3 style={{ marginTop: "8px" }}>Move</h3>
              <p>
                Deposit, withdraw and transfer only from accounts they are
                entitled to.
              </p>
            </div>

            {/* Role 3: Auditor */}
            <div className={`rc rv ${rolesInView ? "in" : ""}`}>
              <div className="viz">
                <small>Ledger integrity</small>
                <div className="vr a1">
                  <span className="mono">#1042 · 7c1a</span>
                  <b className="ok">✓ verified</b>
                </div>
                <div className="vr a2">
                  <span className="mono">#1043 · e90d</span>
                  <b className="ok">✓ verified</b>
                </div>
                <div className="vr a3">
                  <span className="mono">#1044 · 31bf</span>
                  <b className="ok">✓ verified</b>
                </div>
                <div className="vr a4">
                  <span className="mono">Edit attempt</span>
                  <b>✕ rejected</b>
                </div>
              </div>

              <span className="k" style={{ display: "block", marginTop: "22px" }}>
                AUDITOR
              </span>
              <h3 style={{ marginTop: "8px" }}>Verify</h3>
              <p>Read-only access to every posting and every refusal.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Callout Band */}
      <div className={`band ${bandInView ? "in" : ""}`} ref={bandRef}>
        <div className="cols" aria-hidden="true">
          <div>
            {[...matrixLogs, ...matrixLogs].map((log, i) => (
              <p key={`col1-${i}`} style={{ margin: 0 }}>
                {log}
              </p>
            ))}
          </div>
          <div>
            {[...matrixLogs, ...matrixLogs].map((log, i) => (
              <p key={`col2-${i}`} style={{ margin: 0 }}>
                {matrixLogs[(i + 3) % matrixLogs.length]}
              </p>
            ))}
          </div>
          <div>
            {[...matrixLogs, ...matrixLogs].map((log, i) => (
              <p key={`col3-${i}`} style={{ margin: 0 }}>
                {matrixLogs[(i + 6) % matrixLogs.length]}
              </p>
            ))}
          </div>
        </div>

        <div className="in">
          <h2 className={`sp ${bandInView ? "in" : ""}`}>
            <span className="w">
              <span style={{ transitionDelay: "0ms" }}>Nothing</span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "70ms" }}>created.</span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "140ms" }}>
                <em>Nothing</em>
              </span>
            </span>{" "}
            <span className="w">
              <span style={{ transitionDelay: "210ms" }}>
                <em>lost.</em>
              </span>
            </span>
          </h2>
          <a className="btn" href="#top">
            Request a demo
          </a>
        </div>
      </div>

      {/* Footer */}
      <footer>
        <div className="wrap">
          <span>© 2026 LedgerLine</span>
          <span className="mono">Σ in = Σ out</span>
        </div>
      </footer>
    </>
  );
}
