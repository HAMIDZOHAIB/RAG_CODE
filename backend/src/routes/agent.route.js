// backend/src/routes/agent.route.js
import express from "express";
import { agentController } from "../controllers/agentController.js";

const router = express.Router();

// POST /api/agent
router.post("/agent", agentController);

export default router;
