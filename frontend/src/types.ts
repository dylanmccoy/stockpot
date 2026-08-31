export interface Recipe {
  id: number;
  title: string;
  ingredients: string;
  instructions: string;
  created_at: string;
}

export type RecipeInput = Pick<Recipe, "title" | "ingredients" | "instructions">;
