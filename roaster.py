import os, ConfigParser, sys, svn.core, svn.client, svn.wc

def createSVNContext():
  ctx = svn.client.svn_client_ctx_t()
  providers = []
  providers.append(svn.client.get_simple_provider())
  providers.append(svn.client.get_username_provider())
  providers.append(svn.client.get_ssl_server_trust_file_provider())
  providers.append(svn.client.get_ssl_client_cert_file_provider())
  providers.append(svn.client.get_ssl_client_cert_pw_file_provider())
  ctx.auth_baton = svn.core.svn_auth_open(providers)
  ctx.config = svn.core.svn_config_get_config(None)
  return ctx

def changeRevision(ctx, dir, revision):
  path = svn.core.svn_path_canonicalize(dir)
  adm_access = svn.wc.adm_probe_open(None, path, False, False)
  entry = svn.wc.entry(path, adm_access, False)
  if (revision) and (entry.revision == int(revision)):
    return False
  rev = svn.core.svn_opt_revision_t()
  if revision:
    rev.kind = svn.core.svn_opt_revision_number
    rev.value = svn.core.svn_opt_revision_value_t()
    rev.value.number = int(revision)
  else:
    rev.kind = svn.core.svn_opt_revision_head
  newrev = svn.client.update(path, rev, True, ctx)
  if entry.revision != newrev:
    print "  Updated to revision", newrev
    return True
  return False

def getRevision(dir):
  if os.path.isdir(os.path.join(dir, ".svn")):
    path = svn.core.svn_path_canonicalize(dir)
    adm_access = svn.wc.adm_probe_open(None, path, False, False)
    entry = svn.wc.entry(path, adm_access, False)
    return entry.revision
  return None

def getDirs(basedir, dirs, versioned = False):
  results = []
  for dir in dirs:
    if os.path.isdir(os.path.join(basedir, dir)):
      path = os.path.join(basedir, dir)
    else:
      continue
    if versioned:
      if not os.path.isdir(os.path.join(path, ".svn")):
        continue
    if os.path.exists(os.path.join(path, "build", "xpibuild.py")):
      results.append(path)

  return results

def build(dir, release, outputdir):
  revision = getRevision(dir)
  sys.path.append(os.path.join(dir, "build"))
  xpibuild = __import__("xpibuild")
  builder = xpibuild.XPIBuilder()
  builder.release = True
  if not release:
    builder.buildid = "r" + str(revision)

  print "  Building..."
  try:
    builder.init()
    if outputdir:
      builder.outputdir = outputdir.replace("${name}", builder.settings['name'])
    print "  Building to " + builder.outputdir
    builder.clean()
    builder.build()
    builder.package()
  except:
    print "  Build failed"
  sys.path = sys.path[:-1]

def main():
  config = ConfigParser.ConfigParser()
  inifile = os.path.join(os.path.dirname(os.path.dirname(__file__)), "roaster.ini")
  if os.path.exists(inifile):
    config.read(inifile)

  from optparse import OptionParser
  parser = OptionParser("Usage: %prog [options] [directory1] [directory2] .. [directoryn]")
  parser.add_option("-u", "--update", action="store_true", default = False,
                    help="update to the latest revision, only build if there was a change")
  parser.add_option("-r", "--revision", default = None,
                    help="update to a specific revision, only build if there was a change")
  parser.add_option("-f", "--force", action="store_true", default = False,
                    help="force building even if the update made no change")
  parser.add_option("-l", "--release", action="store_true", default = False,
                    help="create release builds with no build identifier")
  parser.add_option("-b", "--basedir", default = None,
                    help="set the base directory of the items")
  (options, items) = parser.parse_args()

  if options.basedir:
    basedir = options.basedir
  else:
    if config.has_option("paths", "roastdir"):
      basedir = config.get("paths", "roastdir")
    else:
      parser.error("no base directory specified on command line or in configuration")
      return

  if not os.path.exists(basedir):
    parser.error("base directory does not exist")
    return

  if options.update and options.revision:
    parser.error("cannot give both -u and -r at the same time")
    return

  if len(items) == 0:
    roasts = getDirs(basedir, os.listdir(basedir), options.update or options.revision)
  else:
    roasts = getDirs(basedir, items, options.update or options.revision)
    if len(roasts) < len(items):
      parser.error("invalid directories specified")
      return

  if len(roasts) == 0:
    parser.error("nothing to do")
    return

  if os.path.exists(os.path.join(basedir, "roast.lock")):
    parser.error("directory is locked")
    return

  if options.release:
    target = "releasedir"
  else:
    target = "outputdir"
  if config.has_option("paths", target):
    outputdir = config.get("paths", target)
  else:
    outputdir = None

  os.mkdir(os.path.join(basedir, "roast.lock"))
  try:
    ctx = createSVNContext()
    for dir in roasts:
      print "Roasting " + dir
      if options.revision or options.update:
        if ((not changeRevision(ctx, dir, options.revision)) and
           (not options.force)):
          print "  No change, skipping"
          continue
      build(dir, options.release, outputdir)
  finally:
    os.rmdir(os.path.join(basedir, "roast.lock"))

main()
