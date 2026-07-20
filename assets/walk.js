/* The lane walk: one engine, shared by healthcare.html, brands.html and ai.html.
   Embla makes the strip follow the finger 1:1 while dragging, then settles to the
   nearest panel. Wheel, swipe, edge taps and the keyboard all feed that same
   engine, so nothing fights. Per-page intros stay in the page; this file is only
   the walk. Load it after /assets/embla-carousel.umd.js. */
(function(){
  var viewport = document.getElementById('track');
  if(!viewport) return;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var panels = [].slice.call(viewport.querySelectorAll('.panel'));
  var cur = 0;

  /* contact overlay: "Talk to me" blurs the page and brings the ways to reach me
     forward. Esc, the close control, or the scrim closes it and unblurs. Focus is
     moved in on open and restored on close, and Tab is trapped inside. */
  var sheet = document.getElementById('talksheet');
  var talkBtn = document.querySelector('[data-talk]');
  var lastFocus = null;
  function openTalk(){
    if(!sheet) return;
    lastFocus = document.activeElement;
    sheet.hidden = false;
    var f = sheet.querySelector('a[href],button');
    if(f) f.focus();
  }
  function closeTalk(){
    if(!sheet || sheet.hidden) return;
    sheet.hidden = true;
    if(lastFocus && lastFocus.focus) lastFocus.focus();
  }
  if(talkBtn) talkBtn.addEventListener('click', function(e){ e.preventDefault(); openTalk(); });
  if(sheet){
    [].forEach.call(sheet.querySelectorAll('[data-talkclose]'), function(el){
      el.addEventListener('click', closeTalk);
    });
    sheet.addEventListener('keydown', function(e){
      if(e.key === 'Escape'){ e.preventDefault(); closeTalk(); return; }
      if(e.key !== 'Tab') return;
      var f = sheet.querySelectorAll('a[href],button');
      if(!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
      else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
    });
  }
  addEventListener('keydown', function(e){
    if(e.key === 'Escape' && sheet && !sheet.hidden){ e.preventDefault(); closeTalk(); }
  });

  /* tick pagination: one mark per panel, the current one emphasized. Marks jump. */
  var ticksWrap = document.getElementById('ticks');
  var ticks = panels.map(function(p, i){
    var b = document.createElement('button');
    b.className = 'tick'; b.type = 'button';
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-label', p.getAttribute('data-name'));
    b.innerHTML = '<i></i>';
    b.addEventListener('click', function(){ toIndex(i); });
    if(ticksWrap) ticksWrap.appendChild(b);
    return b;
  });
  function setPos(i){
    cur = i;
    ticks.forEach(function(b, j){ b.setAttribute('aria-current', j === i ? 'true' : 'false'); });
  }
  setPos(0);

  var embla = window.EmblaCarousel && EmblaCarousel(viewport, {
    axis:'x', loop:false, align:'start', containScroll:'trimSnaps',
    dragFree:false, skipSnaps:false, duration: reduce ? 0 : 28, watchDrag: false
  });
  /* one deliberate gesture = at most one panel. Every advance routes through
     go(), which enforces a cooldown (the transition plus a margin) so a fast
     flick's momentum, a stray edge click, or a second wheel tick cannot chain a
     second step. Direct jumps (ticks, Home/End) bypass the gate. */
  var navLockUntil = 0, NAV_COOL = reduce ? 90 : 480;
  function go(dir){
    if(!embla) return;
    var now = performance.now();
    if(now < navLockUntil) return;
    navLockUntil = now + NAV_COOL;
    if(dir > 0) embla.scrollNext(); else embla.scrollPrev();
  }
  function next(){ go(1); }
  function prev(){ go(-1); }
  function toIndex(i){ if(embla) embla.scrollTo(Math.max(0, Math.min(panels.length - 1, i))); }
  if(embla){
    var sync = function(){ setPos(embla.selectedScrollSnap()); };
    embla.on('select', sync); embla.on('reInit', sync); sync();
  }

  /* slide-with-zoom: tie each panel's scale and opacity to Embla's scroll
     progress so the outgoing panel eases down and softens while the incoming one
     grows into place (the mesura.eu / rauno.me feel). It tracks the movement
     frame by frame. Reduced motion gets a plain cut, no zoom. */
  var pins = panels.map(function(p){ return p.querySelector('.pin'); });
  function applyZoom(){
    var prog = embla.scrollProgress();
    var snaps = embla.scrollSnapList();
    var span = snaps.length > 1 ? snaps.length - 1 : 1;
    snaps.forEach(function(snap, i){
      var pin = pins[i];
      if(!pin) return;
      var norm = Math.min(Math.abs((snap - prog) * span), 1);
      pin.style.transform = 'scale(' + (1 - norm * 0.08).toFixed(4) + ')';
      pin.style.opacity = (1 - norm * 0.4).toFixed(3);
    });
  }
  if(embla && !reduce){
    embla.on('scroll', applyZoom); embla.on('reInit', applyZoom); applyZoom();
  }

  /* Boxes that scroll their own content (the record viewer, the reviews list)
     carry class "scrolls". One rule, everywhere:
       up/down inside such a box scrolls THE BOX, and only turns the page once
       the box has nothing left to give;
       left/right always turns the page, wherever the pointer or finger is.
     Anywhere else, up/down turns the page as before. Nothing traps the walk. */
  /* a box only counts as scrollable when it has a real amount to give. A few
     stray pixels of overflow would otherwise swallow a whole swipe and read as
     a trap. */
  var MIN_OVERFLOW = 24;
  function scrollBox(el){
    while(el && el.nodeType === 1 && el !== viewport){
      if(el.classList && el.classList.contains('scrolls') &&
         el.scrollHeight - el.clientHeight > MIN_OVERFLOW) return el;
      el = el.parentElement;
    }
    return null;
  }
  function hasRoom(box, dy){
    if(!box) return false;
    var max = box.scrollHeight - box.clientHeight;
    if(max <= MIN_OVERFLOW) return false;
    return dy > 0 ? box.scrollTop < max - 1 : box.scrollTop > 1;
  }

  /* mark the boxes that actually overflow so the page can show a cue (a soft
     fade at the bottom edge) only when there is more to read. Re-checked on
     resize and once the images have settled. */
  var boxes = [].slice.call(viewport.querySelectorAll('.scrolls'));
  function markBoxes(){
    boxes.forEach(function(b){
      b.classList.toggle('has-scroll', b.scrollHeight - b.clientHeight > MIN_OVERFLOW);
    });
  }
  markBoxes();
  addEventListener('resize', markBoxes);
  addEventListener('load', markBoxes);
  boxes.forEach(function(b){ b.addEventListener('scroll', function(){
    b.classList.toggle('at-end', b.scrollTop >= b.scrollHeight - b.clientHeight - 2);
  }, {passive:true}); });

  /* wheel/trackpad: one deliberate gesture advances at most one panel.
     This used to lock after a step and only unlock once the wheel went quiet for
     200ms. A trackpad keeps emitting for a second or more after you let go, and
     every event pushed that deadline further out, so anyone who kept swiping
     could never satisfy the unlock and the walk simply stopped responding.
     Nudging the mouse appeared to help only because it interrupted the momentum
     stream.
     Instead: a momentum TAIL is recognised by its shape. Deltas decay as a flick
     dies, so anything well below the strongest delta of the current gesture is
     treated as tail and ignored, while a genuine new push spikes back up and is
     taken immediately. go() still enforces one panel per gesture, so nothing can
     chain even if this is generous. */
  var wheelAcc = 0, wheelIdle = null, boxUntil = 0, gestureMax = 0;
  viewport.addEventListener('wheel', function(e){
    if(e.ctrlKey || e.metaKey) return;
    if(sheet && !sheet.hidden) return;
    var dx = e.deltaX, dy = e.deltaY;
    var vertical = Math.abs(dy) >= Math.abs(dx);
    var delta = vertical ? dy : dx;
    if(!delta) return;
    if(vertical){
      var box = scrollBox(e.target);
      if(hasRoom(box, dy)){
        /* the box takes it, natively. Hold the walk for a moment so a trackpad's
           momentum tail cannot tip the page over the instant the box bottoms out. */
        boxUntil = performance.now() + 320;
        wheelAcc = 0;
        return;
      }
      if(box && performance.now() < boxUntil){ e.preventDefault(); return; }
    }
    e.preventDefault();
    clearTimeout(wheelIdle);
    /* a real pause ends the gesture: forget both the running total and how hard
       the last one was pushed, so the next swipe is judged on its own */
    wheelIdle = setTimeout(function(){ wheelAcc = 0; gestureMax = 0; }, 180);
    var mag = Math.abs(delta);
    if(mag > gestureMax) gestureMax = mag;
    if(gestureMax && mag < gestureMax * 0.45) return;   /* momentum dying away */
    wheelAcc += delta;
    if(Math.abs(wheelAcc) > 40){
      (wheelAcc > 0 ? next() : prev());
      wheelAcc = 0;
      gestureMax = 0;
    }
  }, {passive:false});

  /* touch: a clear sideways swipe turns the page from anywhere, including inside
     a scrolling box. A clear vertical swipe advances too, unless it started in a
     box, in which case the finger was scrolling that box. */
  var txs = 0, tys = 0, tbox = null;
  viewport.addEventListener('touchstart', function(e){
    if(e.touches.length === 1){
      txs = e.touches[0].clientX; tys = e.touches[0].clientY;
      tbox = scrollBox(e.target);
    }
  }, {passive:true});
  viewport.addEventListener('touchend', function(e){
    if(!e.changedTouches.length) return;
    if(sheet && !sheet.hidden) return;
    var dx = e.changedTouches[0].clientX - txs;
    var dy = e.changedTouches[0].clientY - tys;
    var ax = Math.abs(dx), ay = Math.abs(dy);
    /* a deliberate horizontal swipe turns the page; a small/accidental one does not */
    if(ax > 55 && ax > ay * 1.2){ (dx < 0 ? next() : prev()); return; }
    if(tbox) return;                         /* the finger was scrolling that box */
    /* a clear vertical swipe advances too */
    if(ay < 60 || ay < ax * 1.3) return;
    (dy < 0 ? next() : prev());
  }, {passive:true});

  /* edge taps: a quick tap on the outer margin turns the page, but only on
     empty space. A tap on any link or control does that control's action, and
     a drag (pointer moved past a few px) never counts as a tap. */
  var EDGE = 0.22, psx = 0, psy = 0, pt0 = 0, pmax = 0, pdown = false;
  viewport.addEventListener('pointerdown', function(e){
    pdown = true; psx = e.clientX; psy = e.clientY; pt0 = performance.now(); pmax = 0;
  }, {passive:true});
  viewport.addEventListener('pointermove', function(e){
    if(!pdown) return;
    var m = Math.max(Math.abs(e.clientX - psx), Math.abs(e.clientY - psy));
    if(m > pmax) pmax = m;
  }, {passive:true});
  viewport.addEventListener('pointerup', function(e){
    pdown = false;
    if(e.pointerType === 'touch') return;            /* touch is handled on touchend */
    if(sheet && !sheet.hidden) return;
    var dx = e.clientX - psx, dy = e.clientY - psy;
    /* a deliberate horizontal drag turns the page, from anywhere on the panel */
    if(Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.2){ (dx < 0 ? next() : prev()); }
  }, {passive:true});
  viewport.addEventListener('pointercancel', function(){ pdown = false; }, {passive:true});
  viewport.addEventListener('click', function(e){
    if(sheet && !sheet.hidden) return;
    if(pmax > 10 || performance.now() - pt0 > 500) return;   /* a drag or hold, not a tap */
    if(e.target.closest && e.target.closest('a,button,input,textarea,select,summary,label,[role="button"],.scrolls')) return;
    var w = viewport.clientWidth, x = e.clientX;
    if(x < w * EDGE) prev();
    else if(x > w * (1 - EDGE)) next();
  });

  /* a forward step to the next panel */
  [].forEach.call(document.querySelectorAll('[data-next]'), function(b){
    b.addEventListener('click', function(){ next(); });
  });

  /* going home: the same colour flood that brought you into this lane, run again
     on the way out, so leaving matches arriving. Swiping back already felt right
     because the browser handles it; clicking the wordmark used to be a plain
     navigation with nothing in between. */
  var homeLink = document.querySelector('.bandlink');
  var leaving = false;
  if(homeLink && !reduce){
    var floodColor = getComputedStyle(document.documentElement)
      .getPropertyValue('--flood').trim() || '#191814';
    homeLink.addEventListener('click', function(e){
      if(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
      if(leaving) return;
      e.preventDefault();
      leaving = true;
      var d = document.createElement('div');
      d.className = 'flood';
      d.style.background = floodColor;
      var x = e.clientX || innerWidth / 2, y = e.clientY || innerHeight / 2;
      d.style.left = x + 'px'; d.style.top = y + 'px';
      var r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
      d.style.width = d.style.height = (r * 2) + 'px';
      document.body.appendChild(d);
      requestAnimationFrame(function(){ requestAnimationFrame(function(){ d.classList.add('go'); }); });
      setTimeout(function(){ location.href = homeLink.getAttribute('href'); }, 360);
    });
  }
  /* clear a leftover flood when this page is shown again, including a restore
     from the back-forward cache, or an expanded circle would cover the lane */
  window.addEventListener('pageshow', function(){
    leaving = false;
    [].forEach.call(document.querySelectorAll('.flood'), function(f){ f.remove(); });
  });

  addEventListener('keydown', function(e){
    if(sheet && !sheet.hidden) return;
    if(e.altKey || e.metaKey || e.ctrlKey) return;
    if(e.target && e.target.closest && e.target.closest('a,button,input,textarea,select')) {
      if(e.key === ' ' || e.key === 'Enter') return;
    }
    var k = e.key;
    if(k === 'ArrowRight' || k === 'ArrowDown' || k === 'PageDown'){ e.preventDefault(); next(); }
    else if(k === 'ArrowLeft' || k === 'ArrowUp' || k === 'PageUp'){ e.preventDefault(); prev(); }
    else if(k === 'Home'){ e.preventDefault(); toIndex(0); }
    else if(k === 'End'){ e.preventDefault(); toIndex(panels.length - 1); }
  });
})();
