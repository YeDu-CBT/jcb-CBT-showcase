/* 테스트용 window.claude 흉내: db / user / permissions. 설정은 window.__MOCK_CFG 로 넘긴다.
   {uid, base, offline, readonly, noUser, noDb, firstCached(기본 true)} — offline/readonly 는 실행 중에 바꿔도 된다.
   실제 런타임의 규칙을 최대한 따라 한다: 경로 문법(짝수=문서/홀수=컬렉션), 남의 data/users 하위 접근 거절,
   스냅샷 데이터는 얼어 있음, 첫 배달은 fromCache:true. */
(function(){
  var CFG = window.__MOCK_CFG = window.__MOCK_CFG || {};
  var BASE = CFG.base || 'http://localhost:9881';
  var calls = window.__MOCK_CALLS = [];
  function api(method, path, body){
    return fetch(BASE + '/__db/' + path, {method: method, headers: {'content-type': 'application/json'},
      body: body === undefined ? undefined : JSON.stringify(body)}).then(function(r){ return r.json(); });
  }
  function dberr(code, message){ return {code: code, message: message || code}; }
  function segs(p){
    if(typeof p !== 'string' || !p) throw new TypeError('empty path');
    var s = p.split('/');
    s.forEach(function(x){
      if(!/^[A-Za-z0-9_\-.~:@+]+$/.test(x) || x === '.' || x === '..') throw new TypeError('bad segment: ' + x);
      if(new TextEncoder().encode(x).length > 200) throw new TypeError('segment too long');
    });
    if(s.length > 16) throw new TypeError('too deep');
    return s;
  }
  function docPath(p){ var s = segs(p); if(s.length % 2) throw new TypeError('doc path needs even segments: ' + p); return p; }
  function colPath(p){ var s = segs(p); if(s.length % 2 === 0) throw new TypeError('collection path needs odd segments: ' + p); return p; }
  function mine(path){
    var s = path.split('/');
    if(s[0] === 'data' && s[1] === 'users' && s.length >= 3) return s[2] === CFG.uid;
    return true;
  }
  function deepFreeze(o){
    if(o && typeof o === 'object' && !Object.isFrozen(o)){ Object.freeze(o); Object.keys(o).forEach(function(k){ deepFreeze(o[k]); }); }
    return o;
  }
  function checkBody(d){
    if(!d || typeof d !== 'object' || Array.isArray(d)) throw dberr('invalid_argument', 'body must be object');
    var s = JSON.stringify(d);
    if(new TextEncoder().encode(s).length > 256 * 1024) throw dberr('invalid_argument', 'too big');
    return JSON.parse(s);
  }
  function snapOf(id, data, cached){
    var fro = data === undefined ? undefined : deepFreeze(JSON.parse(JSON.stringify(data)));
    return {id: id, exists: data !== undefined, data: function(){ return fro; }, metadata: {fromCache: !!cached, hasPendingWrites: false}};
  }
  function writeGuard(path){
    if(CFG.offline) return dberr('unavailable', 'offline');
    if(CFG.readonly) return dberr('invalid_argument', 'read only');
    if(!mine(path)) return dberr('invalid_argument', 'not yours');
    return null;
  }
  var listeners = [];
  function pump(){
    listeners.forEach(function(L){ if(L.live) L.fetch(false); });
  }
  setInterval(function(){ if(!CFG.offline) pump(); }, 250);

  function makeDocRef(path){
    docPath(path);
    var id = path.split('/').pop();
    return {
      id: id, path: path,
      get: function(){
        if(!mine(path)) return Promise.resolve(snapOf(id, undefined, false));
        return api('GET', 'list?col=' + encodeURIComponent(path.slice(0, path.lastIndexOf('/')))).then(function(r){
          var f = r.docs.filter(function(d){ return d.id === id; })[0];
          return snapOf(id, f ? f.data : undefined, false);
        });
      },
      set: function(data){
        calls.push(['set', path]);
        var g = writeGuard(path); if(g) return Promise.reject(g);
        var body; try{ body = checkBody(data); }catch(e){ return Promise.reject(e); }
        return api('PUT', 'doc?path=' + encodeURIComponent(path), body).then(function(){ pump(); });
      },
      update: function(){ return Promise.reject(dberr('invalid_argument', 'unused in test')); },
      delete: function(){
        calls.push(['delete', path]);
        var g = writeGuard(path); if(g) return Promise.reject(g);
        return api('DELETE', 'doc?path=' + encodeURIComponent(path)).then(function(){ pump(); });
      },
      collection: function(p){ return makeColRef(path + '/' + p); }
    };
  }
  function makeColRef(path){
    colPath(path);
    var ref = {
      path: path,
      doc: function(id){ return makeDocRef(path + '/' + (id || ('auto' + Math.random().toString(36).slice(2, 8)))); },
      add: function(d){ var r = ref.doc(); return r.set(d).then(function(){ return r; }); },
      get: function(){
        return api('GET', 'list?col=' + encodeURIComponent(path)).then(function(r){
          var docs = mine(path) ? r.docs.map(function(d){ return snapOf(d.id, d.data, false); }) : [];
          return {docs: docs, size: docs.length, empty: !docs.length, docChanges: function(){ return []; }, metadata: {fromCache: false, hasPendingWrites: false}};
        });
      },
      where: function(){ return ref; }, orderBy: function(){ return ref; }, limit: function(){ return ref; },
      onSnapshot: function(next, error){
        calls.push(['onSnapshot', path]);
        var L = {live: true, last: null};
        L.fetch = function(first){
          if(!mine(path)){ if(first && error) error(dberr('invalid_argument', 'not yours')); L.live = false; return; }
          api('GET', 'list?col=' + encodeURIComponent(path)).then(function(r){
            if(!L.live) return;
            var sig = JSON.stringify(r.docs);
            if(!first && sig === L.last) return;
            L.last = sig;
            var docs = r.docs.map(function(d){ return snapOf(d.id, d.data, false); });
            next({docs: docs, size: docs.length, empty: !docs.length, docChanges: function(){ return []; }, metadata: {fromCache: false, hasPendingWrites: false}});
          }, function(){});
        };
        listeners.push(L);
        if(CFG.firstCached !== false){
          // 실제 런타임처럼 첫 배달은 '아직 서버 확정본이 아닌' 빈 목록일 수 있다
          setTimeout(function(){
            if(L.live) next({docs: [], size: 0, empty: true, docChanges: function(){ return []; }, metadata: {fromCache: true, hasPendingWrites: false}});
          }, 0);
          setTimeout(function(){ if(L.live) L.fetch(true); }, CFG.firstDelay || 150);
        } else {
          L.fetch(true);
        }
        return function(){ L.live = false; };
      }
    };
    return ref;
  }
  var DB = {doc: makeDocRef, collection: makeColRef};
  var USER = {
    isOwner: function(){ return Promise.resolve(true); },
    canEdit: function(){ return Promise.resolve(true); },
    can: function(){ return Promise.resolve(null); },
    me: function(){ return Promise.resolve({id: CFG.uid, name: '', avatarUrl: '', color: '#000', email: null, isOwner: true, canEdit: true}); },
    id: function(){ return Promise.resolve(CFG.noUser ? null : CFG.uid); },
    profiles: function(){ return Promise.resolve({}); }
  };
  var PERM = {
    state: function(n){ return Promise.resolve(n ? 'granted' : {db: 'granted'}); },
    request: function(){ return Promise.resolve({db: 'granted'}); },
    manage: function(){ window.__MOCK_MANAGE = (window.__MOCK_MANAGE || 0) + 1; return Promise.resolve(); }
  };
  window.claude = {
    use: function(name){
      return new Promise(function(res){
        setTimeout(function(){
          if(name === 'db') res(CFG.noDb ? null : DB);
          else if(name === 'user') res(CFG.noUserCap ? null : USER);
          else if(name === 'permissions') res(PERM);
          else res(null);
        }, CFG.useDelay || 20);
      });
    }
  };
})();
