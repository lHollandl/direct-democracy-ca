import { redirect } from "next/navigation";

/** `/feed` is now `/home` (DEMOCRACY.md §12, ARCHITECTURE.md §9). */
export default function Page() {
  redirect("/home");
}
