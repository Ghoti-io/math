/** @file Float cube-root raw references and caller-state contracts.
 * Copyright 2026 by Corey Pennycuff */
#include "test_helpers.h"
#include "../cbrtf_probe.h"
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>
TEST(Cbrtf, PinnedCorpusAndCallerState) {
  const char *dir=std::getenv("GMATH_CBRTF_CORPUS_DIR");uint64_t hash=0;uint64_t mode_hashes[4]={0};
  EXPECT_EQ(cf_run_record(dir&&*dir?dir:"tests/corpus",1,&hash,mode_hashes),0);
  if (!dir||!*dir) {EXPECT_EQ(hash,GMATH_CBRTF_PINNED_HASH);EXPECT_TRUE(cf_pinned_modes(mode_hashes));}
}
TEST(Cbrtf, GuardedMidpointKeepsPriorBits) {EXPECT_EQ(cf_guard_witness(),0);}
TEST(Cbrtf, EveryBinaryPowerAndSpecialState) {
  fenv_t saved;int saved_errno=errno;ASSERT_EQ(fegetenv(&saved),0);
  const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  for (int e=-149;e<=127;e++) {
    uint32_t a=e>=-126?static_cast<uint32_t>(e+127)<<23:1u<<(e+149);
    for (uint32_t sign:{0u,0x80000000u}) for (int mode:modes) {
      uint32_t output;EXPECT_TRUE(cf_call(a|sign,mode,15,733,&output));
      if (e%3==0) {EXPECT_EQ(output,sign|(static_cast<uint32_t>(e/3+127)<<23));}
    }
  }
  EXPECT_EQ(fesetenv(&saved),0);errno=saved_errno;
}
TEST(Cbrtf, OtherExactCubesRequireInexact) {
  fenv_t saved;int saved_errno=errno;ASSERT_EQ(fegetenv(&saved),0);
  for (float root:{3.f,5.f,7.f,9.f,11.f,13.f}) for (float sign:{-1.f,1.f}) {
    float x=sign*root*root*root;uint32_t output;
    EXPECT_TRUE(cf_call(cf_bits(x),FE_TONEAREST,0,0,&output));EXPECT_EQ(output,cf_bits(sign*root));
  }
  EXPECT_EQ(fesetenv(&saved),0);errno=saved_errno;
}
TEST(Cbrtf, RejectsMalformedReferenceAndRestoresEnvironment) {
  namespace fs=std::filesystem;
  int marker=0;
  auto root=fs::temp_directory_path()/("gmath-cbrtf-"+std::to_string(reinterpret_cast<uintptr_t>(&marker)));
  fs::create_directory(root);
  const std::string header=std::string(CF_PROVENANCE)+"\n# seed 0 count 0 fresh True entries 1\n";
  for (const std::string &body:{std::string("00000000 00000000 00000000 00\nextra\n"),
       std::string("00000000 00000000 00000000 00"),std::string("00000000 80000000 00000000 00\n"),
       std::string("00000000 00000000 00000000 00\n\0",31)}) {
    std::ofstream out(root/"cbrtf-special.corpus",std::ios::binary);out<<header;out.write(body.data(),static_cast<std::streamsize>(body.size()));out.close();
    fenv_t saved;int before_errno=errno;ASSERT_EQ(fegetenv(&saved),0);ASSERT_EQ(fesetround(FE_DOWNWARD),0);
    ASSERT_EQ(feraiseexcept(FE_INVALID|FE_DIVBYZERO),0);int flags=fetestexcept(FE_ALL_EXCEPT);errno=739;
    EXPECT_EQ(cf_run(root.string().c_str(),0),1);EXPECT_EQ(errno,739);EXPECT_EQ(fegetround(),FE_DOWNWARD);EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT),flags);
    EXPECT_EQ(fesetenv(&saved),0);errno=before_errno;
  }
  fs::remove_all(root);
}
TEST(Cbrtf, NormalTableSeamsScaleExactlyUnderNearest) {
  fenv_t saved;int saved_errno=errno;ASSERT_EQ(fegetenv(&saved),0);ASSERT_EQ(fesetround(FE_TONEAREST),0);
  for (int e=-126;e<=127;e++) {
    int q=e/3,r=e%3;if (r<0) {r+=3;--q;}
    for (unsigned j=0;j<=64;j++) for (int delta:{-1,0,1}) {
      int64_t fraction=static_cast<int64_t>(j)*0x20000+delta;
      if (fraction<0||fraction>=0x800000) continue;
      uint32_t base=(static_cast<uint32_t>(r+127)<<23)|static_cast<uint32_t>(fraction);
      uint32_t scaled=(static_cast<uint32_t>(e+127)<<23)|static_cast<uint32_t>(fraction);
      for (uint32_t sign:{0u,0x80000000u}) {
        uint32_t reference=cf_bits(gmath_cbrtf(cf_value(base|sign)));
        uint32_t expected=static_cast<uint32_t>(static_cast<int64_t>(reference)+static_cast<int64_t>(q)*0x800000);
        EXPECT_EQ(cf_bits(gmath_cbrtf(cf_value(scaled|sign))),expected);
      }
    }
  }
  EXPECT_EQ(fesetenv(&saved),0);errno=saved_errno;
}
int main(int argc,char **argv) {::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
