import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "./AppLayout";
import IndexesPage from "./pages/IndexesPage";
import PackagePage from "./pages/PackagePage";
import PackagesPage from "./pages/PackagesPage";
import WheelFilePage from "./pages/WheelFilePage";
import WheelPage from "./pages/WheelPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<IndexesPage />} />
          <Route
            path="/indexes/:name/:version/:variant/packages"
            element={<PackagesPage />}
          />
          <Route
            path="/indexes/:name/:version/:variant/packages/:packageName"
            element={<PackagePage />}
          />
          <Route
            path="/indexes/:name/:version/:variant/packages/:packageName/:filename"
            element={<WheelPage />}
          />
          <Route
            path="/indexes/:name/:version/:variant/packages/:packageName/:filename/files/*"
            element={<WheelFilePage />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
