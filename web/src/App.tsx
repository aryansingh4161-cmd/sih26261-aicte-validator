import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { useSettings } from "./app/settings";
import { Placeholder } from "./pages/Placeholder";
import { Home } from "./pages/Home";
import { States } from "./pages/States";
import { CasePage } from "./pages/Case";

// Hash routes so the static demo works on GitHub Pages without server rewrites.
export function App() {
  const { signedIn } = useSettings();
  return (
    <HashRouter>
      <Routes>
        <Route path="/sign-in" element={<Placeholder name="Sign in" />} />
        <Route path="*" element={signedIn || import.meta.env.DEV ? <Shell><Routes>
          <Route path="/" element={<Home />} />
          <Route path="/states" element={<States />} />
          <Route path="/case/:id/*" element={<CasePage />} />
          <Route path="/calendar" element={<Placeholder name="Calendar" />} />
          <Route path="/letters" element={<Placeholder name="Letters" />} />
          <Route path="/appeals" element={<Placeholder name="Appeals" />} />
          <Route path="/analytics" element={<Placeholder name="Analytics" />} />
          <Route path="/search" element={<Placeholder name="Search" />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes></Shell> : <Navigate to="/sign-in" />} />
      </Routes>
    </HashRouter>
  );
}
