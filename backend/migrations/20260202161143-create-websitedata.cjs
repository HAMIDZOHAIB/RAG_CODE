'use strict';

module.exports = {
  async up(queryInterface, Sequelize) {
    await queryInterface.createTable("WebsiteData", {
      id: {
        type: Sequelize.INTEGER,
        autoIncrement: true,
        primaryKey: true,
        allowNull: false,
      },

      website_id: {
        type: Sequelize.INTEGER,
        allowNull: false,
      },

      website_link: {
        type: Sequelize.STRING,
        allowNull: false,
      },

      plain_text: {
        type: Sequelize.TEXT,
        allowNull: false,
      },

      embedding: {
        type: Sequelize.ARRAY(Sequelize.FLOAT),
        allowNull: false,
      },

      createdAt: {
        allowNull: false,
        type: Sequelize.DATE,
      },

      updatedAt: {
        allowNull: false,
        type: Sequelize.DATE,
      },
    });
  },

  async down(queryInterface, Sequelize) {
    await queryInterface.dropTable("WebsiteData");
  }
};
