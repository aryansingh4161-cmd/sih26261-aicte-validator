import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { useSettings } from "./app/settings";
import { Home } from "./pages/Home";
import { States } from "./pages/States";
import { CasePage } from "./pages/Case";
import { Letters } from "./pages/Letters";
import { SignIn } from "./pages/SignIn";
import { Calendar } from "./pages/Calendar";
import { Appeals } from "./pages/Appeals";
import { Analytics } from "./pages/Analytics";
import { Search } from "./pages/Search";
import { Evc } from "./pages/Evc";
import { Policy } from "./pages/Policy";

const POLICIES = ["privacy", "terms", "accessibility"];
// Hash routes so the static demo works on GitHub Pages without server rewrites.
export function App() {
  const { signedIn } = useSettings();
  return (
    <HashRouter>
      <Routes>
        <Route path="/sign-in" element={<SignIn />} />
        {!signedIn && POLICIES.map((n) => <Route key={n} path={`/${n}`} element={<Policy name={n} />} />)}
        <Route path="*" element={signedIn ? <Shell><Routes>
          <Route path="/" element={<Home />} />
          <Route path="/states" element={<States />} />
          <Route path="/case/:id/*" element={<CasePage />} />
          <Route path="/calendar" element={<Calendar />} />
          <Route path="/letters" element={<Letters />} />
          <Route path="/appeals" element={<Appeals />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/search" element={<Search />} />
          <Route path="/visit/:id" element={<Evc />} />
          {POLICIES.map((n) => <Route key={n} path={`/${n}`} element={<Policy name={n} />} />)}
          <Route path="*" element={<Navigate to="/" />} />
        </Routes></Shell> : <Navigate to="/sign-in" />} />
      </Routes>
    </HashRouter>
  );
}
