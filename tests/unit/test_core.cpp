/**
 * @file
 *
 * The version: the placeholder test the scaffold ships with.
 *
 * Copyright 2026 by Corey Pennycuff
 */

#include "test_helpers.h"

#include <ghoti.io/math/libver.h>

#include <cstring>

TEST(Version, StringMatchesTheGeneratedHeader) {
  EXPECT_STREQ(gmath_version_string(), GMATH_VERSION_STRING);
  EXPECT_EQ(gmath_version_number(), GMATH_VERSION_NUMBER);
  EXPECT_EQ(GMATH_VERSION_NUMBER,
      GMATH_MAKE_VERSION(GMATH_VERSION_MAJOR, GMATH_VERSION_MINOR,
          GMATH_VERSION_PATCH));
}

TEST(Version, StringIsNeverNullOrEmpty) {
  ASSERT_NE(gmath_version_string(), nullptr);
  EXPECT_GT(std::strlen(gmath_version_string()), 0u);
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
