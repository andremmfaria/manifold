import { Module } from '@nestjs/common';
import { AuthModule } from './modules/auth/auth.module';
import { BookmarkModule } from './modules/bookmark/bookmark.module';
import { UserModule } from './modules/user/user.module';

@Module({
  imports: [AuthModule, UserModule, BookmarkModule],
})
export class MainModule {}
