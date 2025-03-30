# Spring 框架
### 1.  什么是 Spring 框架?
Spring 是一款开源的轻量级 Java 开发框架，旨在提高开发人员的开发效率以及系统的可维护性。我们一般说 Spring 框架指的都是 Spring Framework，它是很多模块的集合，使用这些模块可以很方便地协助我们进行开发，比如说 Spring 支持 IoC（Inversion of Control:控制反转） 和 AOP(Aspect-Oriented Programming:面向切面编程)、可以很方便地对数据库进行访问、可以很方便地集成第三方组件


### 2.  Spring 包含的模块有哪些？
Core Container：
Spring 框架的核心模块，也可以说是基础模块，主要提供 IoC 依赖注入功能的支持。Spring 其他所有的功能基本都需要依赖于该模块，我们从上面那张 Spring 各个模块的依赖关系图就可以看出来。
spring-core：Spring 框架基本的核心工具类。
spring-beans：提供对 bean 的创建、配置和管理等功能的支持。
spring-context：提供对国际化、事件传播、资源加载等功能的支持。
spring-expression：提供对表达式语言（Spring Expression Language） SpEL 的支持，只依赖于 core 模块，不依赖于其他模块，可以单独使用。

AOP：
spring-aspects：该模块为与 AspectJ 的集成提供支持。
spring-aop：提供了面向切面的编程实现。
spring-instrument：提供了为 JVM 添加代理（agent）的功能。 具体来讲，它为 Tomcat 提供了一个织入代理，能够为 Tomcat 传递类文 件，就像这些文件是被类加载器加载的一样。没有理解也没关系，这个模块的使用场景非常有限。

Data Access/Integration：
spring-jdbc：提供了对数据库访问的抽象 JDBC。不同的数据库都有自己独立的 API 用于操作数据库，而 Java 程序只需要和 JDBC API 交互，这样就屏蔽了数据库的影响。
spring-tx：提供对事务的支持。
spring-orm：提供对 Hibernate、JPA、iBatis 等 ORM 框架的支持。
spring-oxm：提供一个抽象层支撑 OXM(Object-to-XML-Mapping)，例如：JAXB、Castor、XMLBeans、JiBX 和 XStream 等。
spring-jms : 消息服务。自 Spring Framework 4.1 以后，它还提供了对 spring-messaging 模块的继承。

Spring Web
spring-web：对 Web 功能的实现提供一些最基础的支持。
spring-webmvc：提供对 Spring MVC 的实现。
spring-websocket：提供了对 WebSocket 的支持，WebSocket 可以让客户端和服务端进行双向通信。
spring-webflux：提供对 WebFlux 的支持。WebFlux 是 Spring Framework 5.0 中引入的新的响应式框架。与 Spring MVC 不同，它不需要 Servlet API，是完全异步。


Messaging
spring-messaging 是从 Spring4.0 开始新加入的一个模块，主要职责是为 Spring 框架集成一些基础的报文传送应用。

Spring Test
Spring 团队提倡测试驱动开发（TDD）。有了控制反转 (IoC)的帮助，单元测试和集成测试变得更简单。

### 3.  Spring,Spring MVC,Spring Boot 之间什么关系?
Spring 包含了多个功能模块（上面刚刚提到过），其中最重要的是 Spring-Core（主要提供 IoC 依赖注入功能的支持） 模块， Spring 中的其他模块（比如 Spring MVC）的功能实现基本都需要依赖于该模块。

Spring MVC 是 Spring 中的一个很重要的模块，主要赋予 Spring 快速构建 MVC 架构的 Web 程序的能力。MVC 是模型(Model)、视图(View)、控制器(Controller)的简写，其核心思想是通过将业务逻辑、数据、显示分离来组织代码。

Spring Boot 旨在简化 Spring 开发（减少配置文件，开箱即用！）。

### 4.  谈谈自己对于 Spring IoC 的了解
IoC（Inversion of Control:控制反转） 是一种设计思想，而不是一个具体的技术实现。IoC 的思想就是将原本在程序中手动创建对象的控制权，交由 Spring 框架来管理。不过， IoC 并非 Spring 特有，在其他语言中也有应用。
将对象之间的相互依赖关系交给 IoC 容器来管理，并由 IoC 容器完成对象的注入。这样可以很大程度上简化应用的开发，把应用从复杂的依赖关系中解放出来。 IoC 容器就像是一个工厂一样，当我们需要创建一个对象的时候，只需要配置好配置文件/注解即可，完全不用考虑对象是如何被创建出来的。

### 5.  为什么叫控制反转？
控制：指的是对象创建（实例化、管理）的权力
反转：控制权交给外部环境（Spring 框架、IoC 容器）

### 6.  谈谈自己对于 AOP 的了解？
AOP(Aspect-Oriented Programming:面向切面编程)能够将那些与业务无关，却为业务模块所共同调用的逻辑或责任（例如事务处理、日志管理、权限控制等）封装起来，便于减少系统的重复代码，降低模块间的耦合度，并有利于未来的可拓展性和可维护性。
AOP 切面编程涉及到的一些专业术语：

### 7.  多个切面的执行顺序如何控制？
1.通常使用@Order 注解直接定义切面顺序
2.实现Ordered 接口重写 getOrder 方法。

### 8. IOC和AOP是通过什么机制来实现的?
>Spring IOC 实现机制
- **反射**：Spring IOC容器利用Java的反射机制动态地加载类、创建对象实例及调用对象方法，反射允许在运行时检查类、方法、属性等信息，从而实现灵活的对象实例化和管理。
- **依赖注入**：IOC的核心概念是依赖注入，即容器负责管理应用程序组件之间的依赖关系。Spring通过构造函数注入、属性注入或方法注入，将组件之间的依赖关系描述在配置文件中或使用注解。
- **设计模式 - 工厂模式**：Spring IOC容器通常采用工厂模式来管理对象的创建和生命周期。容器作为工厂负责实例化Bean并管理它们的生命周期，将Bean的实例化过程交给容器来管理。
- **容器实现**：Spring IOC容器是实现IOC的核心，通常使用BeanFactory或ApplicationContext来管理Bean。BeanFactory是IOC容器的基本形式，提供基本的IOC功能；ApplicationContext是BeanFactory的扩展，并提供更多企业级功能。

### 9. 依赖倒置，依赖注入，控制反转分别是什么？
- **控制反转**：“控制”指的是对程序执行流程的控制，而“反转”指的是在没有使用框架之前，程序员自己控制整个程序的执行。在使用框架之后，整个程序的执行流程通过框架来控制。流程的控制权从程序员“反转”给了框架。
- **依赖注入**：依赖注入和控制反转恰恰相反，它是一种具体的编码技巧。我们不通过 new 的方式在类内部创建依赖类的对象，而是将依赖的类对象在外部创建好之后，通过构造函数、函数参数等方式传递（或注入）给类来使用。
- **依赖倒置**：这条原则跟控制反转有点类似，主要用来指导框架层面的设计。高层模块不依赖低层模块，它们共同依赖同一个抽象。抽象不要依赖具体实现细节，具体实现细节依赖抽象。

### 10. 如果让你设计一个SpringIoc，你觉得会从哪些方面考虑这个设计？
- **Bean的生命周期管理**：需要设计Bean的创建、初始化、销毁等生命周期管理机制，可以考虑使用工厂模式和单例模式来实现。
- **依赖注入**：需要实现依赖注入的功能，包括属性注入、构造函数注入、方法注入等，可以考虑使用反射机制和XML配置文件来实现。
- **Bean的作用域**：需要支持多种Bean作用域，比如单例、原型、会话、请求等，可以考虑使用Map来存储不同作用域的Bean实例。
- **AOP功能的支持**：需要支持AOP功能，可以考虑使用动态代理机制和切面编程来实现。
- **异常处理**：需要考虑异常处理机制，包括Bean创建异常、依赖注入异常等，可以考虑使用try-catch机制来处理异常。
- **配置文件加载**：需要支持从不同的配置文件中加载Bean的相关信息，可以考虑使用XML、注解或者Java配置类来实现。

### 11. 你在做系统的过程中的哪些地方用到了aop？
利用AOP可以对我们边缘业务进行隔离，降低无关业务逻辑耦合性。 提高程序的可重用性，同时提高了开发的效率。 一般用于 日志记录，性能统计，安全控制，权限管理，事务处理，异常处理，资源池管理。
### 12. SpringAOP的原理了解吗?
Spring AOP的实现依赖于动态代理技术。动态代理是在运行时动态生成代理对象，而不是在编译时。它允许开发者在运行时指定要代理的接口和行为，从而实现在不修改源码的情况下增强方法的功能。
Spring AOP支持两种动态代理：
- **基于JDK的动态代理**：使用java.lang.reflect.Proxy类和java.lang.reflect.InvocationHandler接口实现。这种方式需要代理的类实现一个或多个接口。
- **基于CGLIB的动态代理**：当被代理的类没有实现接口时，Spring会使用CGLIB库生成一个被代理类的子类作为代理。CGLIB（Code Generation Library）是一个第三方代码生成库，通过继承方式实现代理。



### 13.  什么是 Spring中的Bean？
简单来说，Bean 代指的就是那些被 IoC 容器所管理的对象。我们需要告诉 IoC 容器帮助我们管理哪些对象，这个是通过配置元数据来定义的。配置元数据可以是 XML 文件、注解或者 Java 配置类。

### 14.将一个类声明为 Bean 的注解有哪些?

@Component：通用的注解，可标注任意类为 Spring 组件。如果一个 Bean 不知道属于哪个层，可以使用@Component 注解标注。
@Repository : 对应持久层即 Dao 层，主要用于数据库相关操作。
@Service : 对应服务层，主要涉及一些复杂的逻辑，需要用到 Dao 层。
@Controller : 对应 Spring MVC 控制层，主要用于接受用户请求并调用 Service 层返回数据给前端页面。

### 15.  @Component 和 @Bean 的区别是什么？
@Component 注解作用于类，而@Bean注解作用于方法。@Component通常是通过类路径扫描来自动侦测以及自动装配到 Spring 容器中。
@Bean 注解比 @Component 注解的自定义性更强，而且很多地方我们只能通过 @Bean 注解来注册 bean。

### 16.  @Autowired 和 @Resource 的区别是什么？
1.@Autowired 是 Spring 提供的注解，@Resource 是 JDK 提供的注解。
2.Autowired 默认的注入方式为byType（根据类型进行匹配），@Resource默认注入方式为 byName
3.当一个接口存在多个实现类的情况下，@Autowired 和@Resource都需要通过名称才能正确匹配到对应的 Bean。Autowired 可以通过 @Qualifier 注解来显式指定名称，@Resource可以通过 name 属性来显式指定名称。
4.@Autowired 支持在构造函数、方法、字段和参数上使用。@Resource 主要用于字段和方法上的注入，不支持在构造函数或参数上使用。

### 17. Bean是否单例？
Spring 中的 Bean 默认都是单例的。

就是说，每个Bean的实例只会被创建一次，并且会被存储在Spring容器的缓存中，以便在后续的请求中重复使用。这种单例模式可以提高应用程序的性能和内存效率。

但是，Spring也支持将Bean设置为多例模式，即每次请求都会创建一个新的Bean实例。要将Bean设置为多例模式，可以在Bean定义中通过设置scope属性为"prototype"来实现。

需要注意的是，虽然Spring的默认行为是将Bean设置为单例模式，但在一些情况下，使用多例模式是更为合适的，例如在创建状态不可变的Bean或有状态Bean时。此外，需要注意的是，如果Bean单例是有状态的，那么在使用时需要考虑线程安全性问题。

### 18.  Bean 的作用域有哪些?
Spring 中 Bean 的作用域通常有下面几种：
singleton : IoC 容器中只有唯一的 bean 实例。Spring 中的 bean 默认都是单例的，是对单例设计模式的应用。
prototype : 每次获取都会创建一个新的 bean 实例。也就是说，连续 getBean() 两次，得到的是不同的 Bean 实例。
request （仅 Web 应用可用）: 每一次 HTTP 请求都会产生一个新的 bean（请求 bean），该 bean 仅在当前 HTTP request 内有效。
session （仅 Web 应用可用） : 每一次来自新 session 的 HTTP 请求都会产生一个新的 bean（会话 bean），该 bean 仅在当前 HTTP session 内有效。
application/global-session （仅 Web 应用可用）：每个 Web 应用在启动时创建一个 Bean（应用 Bean），该 bean 仅在当前应用启动时间内有效。
websocket （仅 Web 应用可用）：每一次 WebSocket 会话产生一个新的 bean。

### 19. Spring容器里存的是什么？
在Spring容器中，存储的主要是Bean对象。

Bean是Spring框架中的基本组件，用于表示应用程序中的各种对象。当应用程序启动时，Spring容器会根据配置文件或注解的方式创建和管理这些Bean对象。Spring容器会负责创建、初始化、注入依赖以及销毁Bean对象。

### 20. Bean注入和xml注入最终得到了相同的效果，它们在底层是怎样做的
>XML 注入
使用 XML 文件进行 Bean 注入时，Spring 在启动时会读取 XML 配置文件，以下是其底层步骤：
- **Bean 定义解析**：Spring 容器通过 XmlBeanDefinitionReader类解析 XML 配置文件，读取其中的 <bean> 标签以获取 Bean 的定义信息。
- **注册 Bean 定义**：解析后的 Bean 信息被注册到 BeanDefinitionRegistry（如DefaultListableBeanFactory）中，包括 Bean 的类、作用域、依赖关系、初始化和销毁方法等。
- **实例化和依赖注入**：当应用程序请求某个 Bean 时，Spring 容器会根据已经注册的 Bean 定义：
   首先，使用反射机制创建该 Bean 的实例。
   然后，根据 Bean 定义中的配置，通过 setter 方法、构造函数或方法注入所需的依赖 Bean。
>注解注入
使用注解进行 Bean 注入时，Spring 的处理过程如下：
- **类路径扫描**：当 Spring 容器启动时，它首先会进行类路径扫描，查找带有特定注解（如 @Component、@Service、@Repository 和 @Controller）的类。
- **注册 Bean 定义**：找到的类会被注册到 BeanDefinitionRegistry 中，Spring 容器将为其生成 Bean 定义信息。这通常通过 AnnotatedBeanDefinitionReader 类来实现。
- **依赖注入**：与 XML 注入类似，Spring 在实例化 Bean 时，也会检查字段上是否有@Autowired、@Inject 或 @Resource 注解。如果有，Spring 会根据注解的信息进行依赖注入。
尽管使用的方式不同，但 XML 注入和注解注入在底层的实现机制是相似的，主要体现在以下几个方面：

1. **BeanDefinition**：无论是 XML 还是注解，最终都会生成 BeanDefinition 对象，并存储在同一个 BeanDefinitionRegistry 中。
2. **后处理器**：
   Spring 提供了多个 Bean 后处理器（如 AutowiredAnnotationBeanPostProcessor），用于处理注解（如 @Autowired）的依赖注入。
   对于 XML，Spring 也有相应的后处理器来处理 XML 配置的依赖注入。
3. **依赖查找**：在依赖注入时，Spring 容器会通过ApplicationContext 中的 BeanFactory 方法来查找和注入依赖，无论是通过 XML 还是注解，都会调用类似的查找方法。


### 21.  Bean 是线程安全的吗？
我们这里以最常用的两种作用域 prototype 和 singleton 为例介绍。
几乎所有场景的 Bean 作用域都是使用默认的 singleton ，重点关注 singleton 作用域即可。prototype 作用域下，每次获取都会创建一个新的 bean 实例，不存在资源竞争问题，所以不存在线程安全问题。singleton 作用域下，IoC 容器中只有唯一的 bean 实例，可能会存在资源竞争问题（取决于 Bean 是否有状态）。如果这个 bean 是有状态的话，那就存在线程安全问题（有状态 Bean 是指包含可变的成员变量的对象）。

对于有状态单例 Bean 的线程安全问题，常见的有两种解决办法：
1.在 Bean 中尽量避免定义可变的成员变量。
2.在类中定义一个 ThreadLocal 成员变量，将需要的可变成员变量保存在 ThreadLocal 中（推荐的一种方式）。

### 22.  Bean 的生命周期了解么?
创建 Bean 的实例
Bean 属性赋值/填充
Bean 初始化
销毁 Bean



### 23.  说说自己对于 Spring MVC 了解?
MVC 是模型(Model)、视图(View)、控制器(Controller)的简写，其核心思想是通过将业务逻辑、数据、显示分离来组织代码。
MVC 是一种设计模式，Spring MVC 是一款很优秀的 MVC 框架。Spring MVC 可以帮助我们进行更简洁的 Web 层的开发，并且它天生与 Spring 框架集成。Spring MVC 下我们一般把后端项目分为 Service 层（处理业务）、Dao 层（数据库操作）、Entity 层（实体类）、Controller 层(控制层，返回数据给前台页面)。


### 24.  Spring MVC 的核心组件有哪些？
DispatcherServlet：核心的中央处理器，负责接收请求、分发，并给予客户端响应。
HandlerMapping：处理器映射器，根据 URL 去匹配查找能处理的 Handler ，并会将请求涉及到的拦截器和 Handler 一起封装。
HandlerAdapter：处理器适配器，根据 HandlerMapping 找到的 Handler ，适配执行对应的 Handler；
Handler：请求处理器，处理实际请求的处理器。
ViewResolver：视图解析器，根据 Handler 返回的逻辑视图 / 视图，解析并渲染真正的视图，并传递给 DispatcherServlet 响应客户端

### 25.  Spring 框架中用到了哪些设计模式？
工厂设计模式 : Spring 使用工厂模式通过 BeanFactory、ApplicationContext 创建 bean 对象。
代理设计模式 : Spring AOP 功能的实现。
单例设计模式 : Spring 中的 Bean 默认都是单例的。
模板方法模式 : Spring 中 jdbcTemplate、hibernateTemplate 等以 Template 结尾的对数据库操作的类，它们就使用到了模板模式。
包装器设计模式 : 我们的项目需要连接多个数据库，而且不同的客户在每次访问中根据需要会去访问不同的数据库。这种模式让我们可以根据客户的需求能够动态切换不同的数据源。
观察者模式: Spring 事件驱动模型就是观察者模式很经典的一个应用。
适配器模式 : Spring AOP 的增强或通知(Advice)使用到了适配器模式、spring MVC 中也是用到了适配器模式适配Controller。

### 26.  Spring 循环依赖了解吗，怎么解决？
循环依赖是指 Bean 对象循环引用，是两个或多个 Bean 之间相互持有对方的引用，例如 CircularDependencyA → CircularDependencyB → CircularDependencyA，一般用三级缓存来解决。

Spring 的三级缓存包括：
一级缓存（singletonObjects）：存放最终形态的 Bean（已经实例化、属性填充、初始化），单例池，为“Spring 的单例属性”⽽⽣。一般情况我们获取 Bean 都是从这里获取的，但是并不是所有的 Bean 都在单例池里面，例如原型 Bean 就不在里面。
二级缓存（earlySingletonObjects）：存放过渡 Bean（半成品，尚未属性填充），也就是三级缓存中ObjectFactory产生的对象，与三级缓存配合使用的，可以防止 AOP 的情况下，每次调用ObjectFactory#getObject()都是会产生新的代理对象的。
三级缓存（singletonFactories）：存放ObjectFactory，ObjectFactory的getObject()方法（最终调用的是getEarlyBeanReference()方法）可以生成原始 Bean 对象或者代理对象（如果 Bean 被 AOP 切面代理）。三级缓存只会对单例 Bean 生效。

接下来说一下 Spring 创建 Bean 的流程：
先去 一级缓存 singletonObjects 中获取，存在就返回；
如果不存在或者对象正在创建中，于是去 二级缓存 earlySingletonObjects 中获取；
如果还没有获取到，就去 三级缓存 singletonFactories 中获取，通过执行 ObjectFacotry 的 getObject() 就可以获取该对象，获取成功之后，从三级缓存移除，并将该对象加入到二级缓存中。

整个解决循环依赖的流程如下：
当 Spring 创建 A 之后，发现 A 依赖了 B ，又去创建 B，B 依赖了 A ，又去创建 A；在 B 创建 A 的时候，那么此时 A 就发生了循环依赖，由于 A 此时还没有初始化完成，因此在 一二级缓存 中肯定没有 A；
那么此时就去三级缓存中调用 getObject() 方法去获取 A 的 前期暴露的对象 ，也就是调用上边加入的 getEarlyBeanReference() 方法，生成一个 A 的 前期暴露对象；
然后就将这个 ObjectFactory 从三级缓存中移除，并且将前期暴露对象放入到二级缓存中，那么 B 就将这个前期暴露对象注入到依赖，来支持循环依赖。

### 27.  循环依赖问题是如何通过@Lazy 解决的呢？
首先 Spring 会去创建 A 的 Bean，创建时需要注入 B 的属性；
由于在 A 上标注了 @Lazy 注解，因此 Spring 会去创建一个 B 的代理对象，将这个代理对象注入到 A 中的 B 属性；
之后开始执行 B 的实例化、初始化，在注入 B 中的 A 属性时，此时 A 已经创建完毕了，就可以将 A 给注入进去。

### 28.  Spring 管理事务的方式有几种？
编程式事务：在代码中硬编码(在分布式系统中推荐使用) : 通过 TransactionTemplate或者 TransactionManager 手动管理事务，事务范围过大会出现事务未提交导致超时，因此事务要比锁的粒度更小。
声明式事务：在 XML 配置文件中配置或者直接基于注解（单体应用或者简单业务系统推荐使用） : 实际是通过 AOP 实现（基于@Transactional 的全注解方式使用最多）

### 29.  Spring 事务中哪几种事务传播行为?
事务传播行为是为了解决业务层方法之间互相调用的事务问题。
1.TransactionDefinition.PROPAGATION_REQUIRED使用的最多的一个事务传播行为，我们平时经常使用的@Transactional注解默认使用就是这个事务传播行为。如果当前存在事务，则加入该事务；如果当前没有事务，则创建一个新的事务。

2.TransactionDefinition.PROPAGATION_REQUIRES_NEW创建一个新的事务，如果当前存在事务，则把当前事务挂起。也就是说不管外部方法是否开启事务，Propagation.REQUIRES_NEW修饰的内部方法会新开启自己的事务，且开启的事务相互独立，互不干扰。

3.TransactionDefinition.PROPAGATION_NESTED如果当前存在事务，则创建一个事务作为当前事务的嵌套事务来运行；如果当前没有事务，则该取值等价于TransactionDefinition.PROPAGATION_REQUIRED。

4.TransactionDefinition.PROPAGATION_MANDATORY如果当前存在事务，则加入该事务；如果当前没有事务，则抛出异常。

### 30.  Spring 事务中的隔离级别有哪几种?
TransactionDefinition.ISOLATION_DEFAULT :使用后端数据库默认的隔离级别，MySQL 默认采用的 REPEATABLE_READ 隔离级别 Oracle 默认采用的 READ_COMMITTED 隔离级别.

TransactionDefinition.ISOLATION_READ_UNCOMMITTED :最低的隔离级别，使用这个隔离级别很少，因为它允许读取尚未提交的数据变更，可能会导致脏读、幻读或不可重复读

TransactionDefinition.ISOLATION_READ_COMMITTED : 允许读取并发事务已经提交的数据，可以阻止脏读，但是幻读或不可重复读仍有可能发生

TransactionDefinition.ISOLATION_REPEATABLE_READ : 对同一字段的多次读取结果都是一致的，除非数据是被本身事务自己所修改，可以阻止脏读和不可重复读，但幻读仍有可能发生。

TransactionDefinition.ISOLATION_SERIALIZABLE : 最高的隔离级别，完全服从 ACID 的隔离级别。所有的事务依次逐个执行，这样事务之间就完全不可能产生干扰，也就是说，该级别可以防止脏读、不可重复读以及幻读。但是这将严重影响程序的性能。通常情况下也不会用到该级别。

### 31. Spring的事务什么情况下会失效？
Spring Boot通过Spring框架的事务管理模块来支持事务操作。事务管理在Spring Boot中通常是通过 @Transactional 注解来实现的。事务可能会失效的一些常见情况包括:
1. **未捕获异常**: 如果一个事务方法中发生了未捕获的异常，并且异常未被处理或传播到事务边界之外，那么事务会失效，所有的数据库操作会回滚。
2. **非受检异常**: 默认情况下，Spring对非受检异常（RuntimeException或其子类）进行回滚处理，这意味着当事务方法中抛出这些异常时，事务会回滚。
3. **事务传播属性设置不当**: 如果在多个事务之间存在事务嵌套，且事务传播属性配置不正确，可能导致事务失效。特别是在方法内部调用有 @Transactional 注解的方法时要特别注意。
4. **多数据源的事务管理**: 如果在使用多数据源时，事务管理没有正确配置或者存在多个 @Transactional 注解时，可能会导致事务失效。
5. **跨方法调用事务问题**: 如果一个事务方法内部调用另一个方法，而这个被调用的方法没有 @Transactional 注解，这种情况下外层事务可能会失效。
6. **事务在非公开方法中失效**: 如果 @Transactional 注解标注在私有方法上或者非 public 方法上，事务也会失效。



### 32.  @Transactional(rollbackFor = Exception.class)注解了解吗？
Exception 分为运行时异常 RuntimeException 和非运行时异常。事务管理对于企业应用来说是至关重要的，即使出现异常情况，它也可以保证数据的一致性。

@Transactional 注解默认回滚策略是只有在遇到RuntimeException(运行时异常) 或者 Error 时才会回滚事务，而不会回滚 Checked Exception（受检查异常）。这是因为 Spring 认为RuntimeException和 Error 是不可预期的错误，而受检异常是可预期的错误，可以通过业务逻辑来处理。
如果想要修改默认的回滚策略，可以使用 @Transactional 注解的 rollbackFor 和 noRollbackFor 属性来指定哪些异常需要回滚，哪些异常不需要回滚.

### 33.  spring容器的启动流程？
1、初始化Spring容器，注册内置的BeanPostProcessor的BeanDefinition到容器中
1、spring容器的初始化时，通过this()调用了无参构造函数，主要做了以下三个事情：

（1）实例化BeanFactory【DefaultListableBeanFactory】工厂，用于生成Bean对象
（2）实例化BeanDefinitionReader注解配置读取器，用于对特定注解（如@Service、@Repository）的类进行读取转化成  BeanDefinition 对象，（BeanDefinition 是 Spring 中极其重要的一个概念，它存储了 bean 对象的所有特征信息，如是否单例，是否懒加载，factoryBeanName 等）
（3）实例化ClassPathBeanDefinitionScanner路径扫描器，用于对指定的包目录进行扫描查找 bean 对象
2.解析用户传入的 Spring 配置类，解析成一个 BeanDefinition 然后注册到容器中
3.调用refresh()方法刷新容器



# SpringBoot
### 为什么使用springboot?
- **简化开发**：Spring Boot通过提供一系列的开箱即用的组件和自动配置，简化了项目的配置和开发过程，开发人员可以更专注于业务逻辑的实现，而不需要花费过多时间在繁琐的配置上。
- **快速启动**：Spring Boot提供了快速的应用程序启动方式，可通过内嵌的Tomcat、Jetty或Undertow等容器快速启动应用程序，无需额外的部署步骤，方便快捷。
- **自动化配置**：Spring Boot通过自动配置功能，根据项目中的依赖关系和约定俗成的规则来配置应用程序，减少了配置的复杂性，使开发者更容易实现应用的最佳实践。


### SpringBoot比Spring好在哪里?
- Spring Boot 提供了自动化配置，大大简化了项目的配置过程。通过约定优于配置的原则，很多常用的配置可以自动完成，开发者可以专注于业务逻辑的实现。
- Spring Boot 提供了快速的项目启动器，通过引入不同的 Starter，可以快速集成常用的框架和库如数据库、消息队列、Web 开发等），极大地提高了开发效率。
- Spring Boot 默认集成了多种内嵌服务器（如Tomcat、Jetty、Undertow），无需额外配置，即可将应用打包成可执行的 JAR 文件，方便部署和运行。


### SpringBoot的自动装配原理？
1. 从 spring.factories 配置文件中加载自动配置类；
2. 加载的自动配置类中排除掉@EnableAutoConfiguration注解的exclude属性指定的自动配置类；
3. 然后再用AutoConfigurationImportFilter接口去过滤自动配置类是否符合其标注注解（若有标注的话）@ConditionalOnClass,@ConditionalOnBean和@ConditionalOnWebApplication的条件，若都符合的话则返回匹配结果；
4. 然后触发AutoConfigurationImportEvent事件，告诉ConditionEvaluationReport条件评估报告器对象来分别记录符合条件和exclude的自动配置类。
5. 最后 spring 再将最后筛选后的自动配置类导入 IOC 容器中
   
### springboot的启动流程？
- 首先从main找到run()方法，在执行run()方法之前new一个SpringApplication对象
- 进入run()方法，创建应用监听器SpringApplicationRunListeners开始监听
- 然后加载SpringBoot配置环境(ConfigurableEnvironment)，然后把配置环境(Environment)加入监听对象中
- 然后加载应用上下文(ConfigurableApplicationContext)，当做run方法的返回对象
- 最后创建Spring容器，refreshContext(context)，实现starter自动化配置和bean的实例化等工作。

### 说几个启动器starter？
- **spring-boot-starter-web**：这是最常用的起步依赖之一，它包含了Spring MVC和Tomcat嵌入式服务器，用于快速构建Web应用程序。
- **spring-boot-starter-security**：提供了Spring Security的基本配置，帮助开发者快速实现应用的安全性，包括认证和授权功能。
- **mybatis-spring-boot-starter**：这个Starter是由MyBatis团队提供的，用于简化在Spring Boot应用中集成MyBatis的过程。它自动配置了MyBatis的相关组件，包括SqlSessionFactory、MapperScannerConfigurer等，使得开发者能够快速地开始使用MyBatis进行数据库操作。
- **spring-boot-starter-data-jpa** 或 **spring-boot-starter-jdbc**：如果使用的是Java Persistence API (JPA)进行数据库操作，那么应该使用spring-boot-starter-data-jpa。这个Starter包含了Hibernate等JPA实现以及数据库连接池等必要的库，可以让你轻松地与MySQL数据库进行交互。你需要在application.properties或application.yml中配置MySQL的连接信息。如果倾向于直接使用JDBC而不通过JPA，那么可以使用spring-boot-starter-jdbc，它提供了基本的JDBC支持。
- **spring-boot-starter-data-redis**：用于集成Redis缓存和数据存储服务。这个Starter包含了与Redis交互所需的客户端（默认是Jedis客户端，也可以配置为Lettuce客户端），以及Spring Data Redis的支持，使得在Spring Boot应用中使用Redis变得非常便捷。同样地，需要在配置文件中设置Redis服务器的连接详情。
- **spring-boot-starter-test**：包含了单元测试和集成测试所需的库，如JUnit, Spring Test, AssertJ等，便于进行测试驱动开发(TDD)。


### SpringBoot里面有哪些重要的注解？还有一个配置相关的注解是哪个？
Spring Boot 中一些常用的注解包括：

- **@SpringBootApplication**：用于标注主应用程序类，标识一个Spring Boot应用程序的入口点，同时启用自动配置和组件扫描。
- **@Controller**：标识控制器类，处理HTTP请求。
- **@RestController**：结合@Controller和@ResponseBody，返回RESTful风格的数据。
- **@Service**：标识服务类，通常用于标记业务逻辑层。
- **@Repository**：标识数据访问组件，通常用于标记数据访问层。
- **@Component**：通用的Spring组件注解，表示一个受Spring管理的组件。
- **@Autowired**：用于自动装配Spring Bean。
- **@Value**：用于注入配置属性值。
- **@RequestMapping**：用于映射HTTP请求路径到Controller的处理方法。
- **@GetMapping、@PostMapping、@PutMapping、@DeleteMapping**：简化@RequestMapping的GET、POST、PUT和DELETE请求。

另外，一个与配置相关的重要注解是：
- **@Configuration**：用于指定一个类为配置类，其中定义的bean会被Spring容器管理。通常与@Bean配合使用，@Bean用于声明一个Bean实例，由Spring容器进行管理。


### springboot怎么开启事务？
在 Spring Boot 中开启事务非常简单，只需在服务层的方法上添加 @Transactional 注解即可。

# Mybatis
### 与传统的JDBC相比，MyBatis的优点？
- 基于 SQL 语句编程，相当灵活，不会对应用程序或者数据库的现有设计造成任 何影响，SQL 写在 XML 里，解除 sql 与程序代码的耦合，便于统一管理；提供 XML 标签，支持编写动态 SQL 语句，并可重用。
- 与 JDBC 相比，减少了 50%以上的代码量，消除了 JDBC 大量冗余的代码，不 需要手动开关连接；
- 很好的与各种数据库兼容，因为 MyBatis 使用 JDBC 来连接数据库，所以只要 JDBC 支持的数据库 MyBatis 都支持。
- 能够与 Spring 很好的集成，开发效率高
- 提供映射标签，支持对象与数据库的 ORM 字段关系映射；提供对象关系映射 标签，支持对象关系组件维护。

### 还记得JDBC连接数据库的步骤吗？
使用Java JDBC连接数据库的一般步骤如下：
1. **加载数据库驱动程序**：在使用JDBC连接数据库之前，需要加载相应的数据库驱动程序。可以通过 Class.forName("com.mysql.jdbc.Driver") 来加载MySQL数据库的驱动程序。不同数据库的驱动类名会有所不同。
2. **建立数据库连接**：使用 DriverManager 类的 getConnection(url, username, password) 方法来连接数据库，其中url是数据库的连接字符串（包括数据库类型、主机、端口等）、username是数据库用户名，password是密码。
3. **创建 Statement 对象**：通过 Connection 对象的createStatement() 方法创建一个 Statement 对象，用于执行 SQL 查询或更新操作。
4. **执行 SQL 查询或更新操作**：使用 Statement 对象的 executeQuery(sql) 方法来执行 SELECT 查询操作，或者使用 executeUpdate(sql)方法来执行 INSERT、UPDATE 或 DELETE 操作。
5. **处理查询结果**：如果是 SELECT 查询操作，通过 ResultSet 对象来处理查询结果。可以使用 ResultSet 的 next() 方法遍历查询结果集，然后通过 getXXX() 方法获取各个字段的值。
6. **关闭连接**：在完成数据库操作后，需要逐级关闭数据库连接相关对象，即先关闭 ResultSet，再关闭 Statement，最后关闭 Connection。


### 如果项目中要用到原生的mybatis去查询，该怎样写？
步骤概述：
1. 配置MyBatis： 在项目中配置MyBatis的数据源、SQL映射文件等。
2. 创建实体类： 创建用于映射数据库表的实体类。
3. 编写SQL映射文件： 创建XML文件，定义SQL语句和映射关系。
4. 编写DAO接口： 创建DAO接口，定义数据库操作的方法。
5. 编写具体的SQL查询语句： 在DAO接口中定义查询方法，并在XML文件中编写对应的SQL语句。
6. 调用查询方法： 在服务层或控制层调用DAO接口中的方法进行查询。

### Mybatis里的 # 和 $ 的区别？
- Mybatis 在处理 #{} 时，会创建预编译的 SQL 语句，将 SQL 中的 #{} 替换为 ? 号，在执行 SQL 时会为预编译 SQL 中的占位符（?）赋值，调用PreparedStatement 的 set 方法来赋值，预编译的 SQL 语句执行效率高，并且可以防止SQL 注入，提供更高的安全性，适合传递参数值。
- Mybatis 在处理 ${} 时，只是创建普通的 SQL 语句，然后在执行 SQL 语句时 MyBatis 将参数直接拼入到 SQL 里，不能防止 SQL 注入，因为参数直接拼接到 SQL 语句中，如果参数未经过验证、过滤，可能会导致安全问题。
  

### MybatisPlus和Mybatis的区别？
MybatisPlus是一个基于MyBatis的增强工具库，旨在简化开发并提高效率。以下是MybatisPlus和MyBatis之间的一些主要区别：

- **CRUD操作**：MybatisPlus通过继承BaseMapper接口，提供了一系列内置的快捷方法，使得CRUD操作更加简单，无需编写重复的SQL语句。
- **代码生成器**：MybatisPlus提供了代码生成器功能，可以根据数据库表结构自动生成实体类、Mapper接口以及XML映射文件，减少了手动编写的工作量。
- **通用方法封装**：MybatisPlus封装了许多常用的方法，如条件构造器、排序、分页查询等，简化了开发过程，提高了开发效率。
- **分页插件**：MybatisPlus内置了分页插件，支持各种数据库的分页查询，开发者可以轻松实现分页功能，而在传统的MyBatis中，需要开发者自己手动实现分页逻辑。
- **多租户支持**：MybatisPlus提供了多租户的支持，可以轻松实现多租户数据隔离的功能。
- **注解支持**：MybatisPlus引入了更多的注解支持，使得开发者可以通过注解来配置实体与数据库表之间的映射关系，减少了XML配置文件的编写。


# SpingCloud
### 了解SpringCloud吗，说一下他和SpringBoot的区别?
Spring Boot是用于构建单个Spring应用的框架，而Spring Cloud则是用于构建分布式系统中的微服务架构的工具，Spring Cloud提供了服务注册与发现、负载均衡、断路器、网关等功能。
两者可以结合使用，通过Spring Boot构建微服务应用，然后用Spring Cloud来实现微服务架构中的各种功能。

### 用过哪些微服务组件？
- **注册中心**：注册中心是微服务架构最核心的组件。它起到的作用是对新节点的注册与状态维护，解决了「如何发现新节点以及检查各节点的运行状态的问题」。
- **负载均衡**：负载均衡解决了「如何发现服务及负载均衡如何实现的问题」，通常微服务在互相调用时，并不是直接通过IP、端口进行访问调用。
- **服务通信**：服务通信组件解决了「服务间如何进行消息通信的问题」，服务间通信采用轻量级协议，通常是HTTP RESTful风格。
- **配置中心**：配置中心主要解决了「如何集中管理各节点配置文件的问题」，在微服务架构下，所有的微服务节点都包含自己的各种配置文件，如jdbc配置、自定义配置、环境配置、运行参数配置等。
- **集中式日志管理**：集中式日志主要是解决了「如何收集各节点日志并统一管理的问题」。
- **分布式链路追踪**：分布式链路追踪解决了「如何直观的了解各节点间的调用链路的问题」。
- **服务保护**：服务保护主要是解决了「如何对系统进行链路保护，避免服务雪崩的问题」。


### 负载均衡有哪些算法？
- **简单轮询**：将请求按顺序分发给后端服务器上，不关心服务器当前的状态，比如后端服务器的性能、当前的负载。
- **加权轮询**：根据服务器自身的性能给服务器设置不同的权重，将请求按顺序和权重分发给后端服务器，可以让性能高的机器处理更多的请求
- **简单随机**：将请求随机分发给后端服务器上，请求越多，各个服务器接收到的请求越平均
- **加权随机**：根据服务器自身的性能给服务器设置不同的权重，将请求按各个服务器的权重随机分发给后端服务器
- **一致性哈希**：根据请求的客户端 ip、或请求参数通过哈希算法得到一个数值，利用该数值取模映射出对应的后端服务器,这样能保证同一个客户端或相同参数的请求每次都使用同一台服务器.
- **最小活跃数**：统计每台服务器上当前正在处理的请求数，也就是请求活跃数，将请求分发给活跃数最少的后台服务器


### 如何实现一直均衡给一个用户？
可以通过「一致性哈希算法」来实现，根据请求的客户端 ip、或请求参数通过哈希算法得到一个数值，利用该数值取模映射出对应的后端服务器，这样能保证同一个客户端或相同参数的请求每次都使用同一台服务器。
