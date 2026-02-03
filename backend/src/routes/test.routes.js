import { Router } from "express";
import { helloWorld } from "../controllers/test.controller.js";

const router = Router();
router.get("/hello", helloWorld);

export default router;
