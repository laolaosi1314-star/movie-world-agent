import { createContext, useContext, useState } from "react";
import { Routes, Route, NavLink, useNavigate } from "react-router-dom";
import Login from "./pages/Login";
import Portal from "./pages/Portal";
import CharacterArchive from "./pages/CharacterArchive";
import WorldControl from "./pages/WorldControl";
import { getToken, isDemo, setToken, setDemo, setWorldId, logout as clearAuth } from "./lib/auth";
import { getWorldId } from "./lib/api";

interface Session {
  token: string | null;
  demo: boolean;
  worldId: number;
}
interface AuthCtx {
  session: Session;
  login: (token: string | null, demo: boolean, worldId: number) => void;
  logout: () => void;
}

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);
export const useAuth = () => useContext(Ctx);

export default function App() {
  const [session, setSession] = useState<Session>(() => ({
    token: getToken(),
    demo: isDemo(),
    worldId: getWorldId(),
  }));

  const login = (token: string | null, demo: boolean, worldId: number) => {
    setToken(token);
    setDemo(demo);
    setWorldId(worldId);
    setSession({ token, demo, worldId });
  };
  const logout = () => {
    clearAuth();
    setSession({ token: null, demo: false, worldId: 1 });
  };

  // 未登录且非演示 → 登录页
  if (!session.token && !session.demo) {
    return (
      <Ctx.Provider value={{ session, login, logout }}>
        <Login />
      </Ctx.Provider>
    );
  }

  return (
    <Ctx.Provider value={{ session, login, logout }}>
      <div className="app">
        <TopBar />
        <div className="content">
          <Routes>
            <Route path="/" element={<Portal />} />
            <Route path="/archive" element={<CharacterArchive />} />
            <Route path="/control" element={<WorldControl />} />
          </Routes>
        </div>
        <Nav />
      </div>
    </Ctx.Provider>
  );
}

function TopBar() {
  const { session, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="topbar">
      <h1>影视世界 · Agent</h1>
      <div className="row">
        <span className="role-chip">{session.demo ? "演示" : "GM"}</span>
        <button className="ghost" onClick={() => { logout(); nav("/"); }}>退出</button>
      </div>
    </div>
  );
}

function Nav() {
  const item = ({ isActive }: any) => "nav-link" + (isActive ? " active" : "");
  return (
    <div className="nav">
      <NavLink to="/" className={item}>首页</NavLink>
      <NavLink to="/archive" className={item}>人物档案</NavLink>
      <NavLink to="/control" className={item}>GM 工作台</NavLink>
    </div>
  );
}
