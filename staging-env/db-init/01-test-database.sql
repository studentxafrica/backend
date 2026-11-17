-- A second database for running the backend test suite against MariaDB.
CREATE DATABASE IF NOT EXISTS studentx_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON studentx_test.* TO 'studentx'@'%';
-- Used by the backup drill to restore into.
CREATE DATABASE IF NOT EXISTS studentx_restore CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON studentx_restore.* TO 'studentx'@'%';
FLUSH PRIVILEGES;
