#import <Cocoa/Cocoa.h>

static NSString *const HelperPath = @"/Library/PrivilegedHelperTools/awg-home/awg_home_helper.py";

@interface AWGController : NSObject <NSApplicationDelegate>
@property (strong) NSWindow *window;
@property (strong) NSTextField *status;
@property (strong) NSButton *connectButton;
@property (strong) NSButton *disconnectButton;
@property (assign) BOOL busy;
@end

@implementation AWGController

- (NSTextField *)label:(NSString *)text frame:(NSRect)frame size:(CGFloat)size {
    NSTextField *label = [[NSTextField alloc] initWithFrame:frame];
    label.stringValue = text;
    label.font = [NSFont systemFontOfSize:size];
    label.bezeled = NO;
    label.drawsBackground = NO;
    label.editable = NO;
    label.selectable = YES;
    return label;
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    (void)notification;
    self.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 440, 215)
        styleMask:(NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable)
        backing:NSBackingStoreBuffered defer:NO];
    self.window.title = @"AWG Home";
    [self.window center];

    NSView *content = self.window.contentView;
    [content addSubview:[self label:@"AWG Home" frame:NSMakeRect(24, 169, 390, 28) size:22]];
    [content addSubview:[self label:@"Личный AmneziaWG на этом Mac"
                                  frame:NSMakeRect(24, 141, 390, 20) size:13]];
    self.status = [self label:@"Проверка состояния…"
                         frame:NSMakeRect(24, 107, 390, 22) size:14];
    [content addSubview:self.status];

    self.connectButton = [[NSButton alloc] initWithFrame:NSMakeRect(24, 54, 180, 38)];
    self.connectButton.title = @"Подключить";
    self.connectButton.bezelStyle = NSBezelStyleRounded;
    self.connectButton.target = self;
    self.connectButton.action = @selector(connect:);
    [content addSubview:self.connectButton];

    self.disconnectButton = [[NSButton alloc] initWithFrame:NSMakeRect(214, 54, 180, 38)];
    self.disconnectButton.title = @"Отключить";
    self.disconnectButton.bezelStyle = NSBezelStyleRounded;
    self.disconnectButton.target = self;
    self.disconnectButton.action = @selector(disconnect:);
    [content addSubview:self.disconnectButton];

    [content addSubview:[self label:@"Для изменения сети macOS запросит пароль администратора."
                                  frame:NSMakeRect(24, 17, 400, 20) size:11]];
    [self.window makeKeyAndOrderFront:nil];
    [NSApp activateIgnoringOtherApps:YES];
    [self refreshStatus];
    [NSTimer scheduledTimerWithTimeInterval:5.0 target:self
                                   selector:@selector(refreshStatus)
                                   userInfo:nil repeats:YES];
}

- (NSString *)runProgram:(NSString *)program arguments:(NSArray<NSString *> *)arguments
                    error:(NSError **)error {
    NSTask *task = [[NSTask alloc] init];
    task.executableURL = [NSURL fileURLWithPath:program];
    task.arguments = arguments;
    NSPipe *output = [NSPipe pipe];
    NSPipe *errors = [NSPipe pipe];
    task.standardOutput = output;
    task.standardError = errors;
    if (![task launchAndReturnError:error]) return nil;
    [task waitUntilExit];
    NSData *data = [[output fileHandleForReading] readDataToEndOfFile];
    NSData *errorData = [[errors fileHandleForReading] readDataToEndOfFile];
    NSString *answer = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding] ?: @"";
    NSString *detail = [[NSString alloc] initWithData:errorData encoding:NSUTF8StringEncoding] ?: @"";
    if (task.terminationStatus != 0) {
        NSString *message = detail.length ? detail : @"Операция не выполнена";
        if (error) *error = [NSError errorWithDomain:@"AWGHome" code:task.terminationStatus
                                           userInfo:@{NSLocalizedDescriptionKey: message}];
        return nil;
    }
    return [answer stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
}

- (void)refreshStatus {
    if (self.busy) return;
    if (![[NSFileManager defaultManager] isExecutableFileAtPath:HelperPath]) {
        self.status.stringValue = @"Нужна первоначальная установка помощника";
        self.connectButton.enabled = NO;
        self.disconnectButton.enabled = NO;
        return;
    }
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        NSError *error = nil;
        NSString *answer = [self runProgram:@"/usr/bin/python3"
                                  arguments:@[HelperPath, @"status"] error:&error];
        dispatch_async(dispatch_get_main_queue(), ^{
            if (self.busy) return;
            BOOL connected = [answer isEqualToString:@"Подключено"];
            self.status.stringValue = error ? @"Не удалось проверить состояние" :
                                      (connected ? @"Подключено" : @"Отключено");
            self.connectButton.enabled = !connected;
            self.disconnectButton.enabled = connected;
        });
    });
}

- (void)performAction:(NSString *)action {
    self.busy = YES;
    self.connectButton.enabled = NO;
    self.disconnectButton.enabled = NO;
    self.status.stringValue = [action isEqualToString:@"start"] ? @"Подключение…" : @"Отключение…";
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        // The action is an internal constant, never untrusted text.
        NSString *command = [NSString stringWithFormat:
            @"/usr/bin/python3 /Library/PrivilegedHelperTools/awg-home/awg_home_helper.py %@", action];
        NSString *script = [NSString stringWithFormat:
            @"do shell script \"%@\" with administrator privileges", command];
        NSError *error = nil;
        NSString *answer = [self runProgram:@"/usr/bin/osascript"
                                  arguments:@[@"-e", script] error:&error];
        dispatch_async(dispatch_get_main_queue(), ^{
            self.busy = NO;
            if (error) {
                NSAlert *alert = [[NSAlert alloc] init];
                alert.messageText = @"AWG Home";
                alert.informativeText = error.localizedDescription;
                [alert runModal];
            } else if (answer.length) {
                self.status.stringValue = answer;
            }
            [self refreshStatus];
        });
    });
}

- (void)connect:(id)sender { (void)sender; [self performAction:@"start"]; }
- (void)disconnect:(id)sender { (void)sender; [self performAction:@"stop"]; }

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    (void)sender;
    return YES;
}

@end

int main(int argc, const char *argv[]) {
    (void)argc;
    (void)argv;
    @autoreleasepool {
        NSApplication *application = [NSApplication sharedApplication];
        AWGController *controller = [[AWGController alloc] init];
        application.delegate = controller;
        [application setActivationPolicy:NSApplicationActivationPolicyRegular];
        [application run];
    }
    return 0;
}
