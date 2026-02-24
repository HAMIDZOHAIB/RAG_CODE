'use strict';

/** @type {import('sequelize-cli').Migration} */
module.exports = {
  async up(queryInterface, Sequelize) {
    // Drop old embedding column (whatever dimension it was)
    await queryInterface.removeColumn('WebsiteData', 'embedding');

    // Add new embedding column with 1024 dimensions for mxbai-embed-large-v1
    await queryInterface.sequelize.query(
      `ALTER TABLE "WebsiteData" ADD COLUMN embedding vector(1024);`
    );
  },

  async down(queryInterface, Sequelize) {
    await queryInterface.removeColumn('WebsiteData', 'embedding');

    // Restore to 384 if rolling back
    await queryInterface.sequelize.query(
      `ALTER TABLE "WebsiteData" ADD COLUMN embedding vector(384);`
    );
  }
};
