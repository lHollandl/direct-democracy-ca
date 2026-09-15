import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Every rule and its value",
};

export default function Page() {
  return <PageClient />;
}
