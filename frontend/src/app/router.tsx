import { Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { RequireAuth } from "./RequireAuth";
import Login from "../pages/Login";
import RecipeList from "../pages/RecipeList";
import RecipeDetail from "../pages/RecipeDetail";
import RecipeForm from "../pages/RecipeForm";
import Inventory from "../pages/Inventory";
import GroceryLists from "../pages/GroceryLists";
import GroceryListDetail from "../pages/GroceryListDetail";
import History from "../pages/History";
import NotFound from "../pages/NotFound";

// Classic component routing (docs/frontend/spec.md §3). TanStack Query owns data;
// there are no data-router loaders/actions.
export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<RecipeList />} />
        <Route path="/recipes/new" element={<RecipeForm mode="create" />} />
        <Route path="/recipes/:id" element={<RecipeDetail />} />
        <Route path="/recipes/:id/edit" element={<RecipeForm mode="edit" />} />
        <Route path="/inventory" element={<Inventory />} />
        <Route path="/groceries" element={<GroceryLists />} />
        <Route path="/groceries/:id" element={<GroceryListDetail />} />
        <Route path="/history" element={<History />} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
