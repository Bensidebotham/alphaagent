import { config } from "dotenv";
import { defineConfig } from "prisma/config";

// Relative to process.cwd() (dashboard/), so ../.env is the project root .env
config({ path: "../.env" });

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: {
    path: "prisma/migrations",
  },
  datasource: {
    url: process.env["DATABASE_URL"],
  },
});
