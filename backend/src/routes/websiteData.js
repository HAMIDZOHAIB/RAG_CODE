import express from "express";
import { createWebsiteData } from "../controllers/websiteDataController.js";

const router = express.Router();

// POST endpoint for Python script
router.post("/", createWebsiteData);

export default router;
